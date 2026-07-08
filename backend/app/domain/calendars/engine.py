"""
Calendar generation engine.

Pure domain logic: no SQLAlchemy, no repository calls, no DB access.
All data is pre-loaded by the service layer and passed in via GenerationContext.
"""

import calendar as cal_module
from dataclasses import dataclass
from datetime import date, timedelta

from backend.app.domain.availability_rules import matches_recurring_monthly_rule
from backend.app.domain.calendars.cp_model import OrToolsEngine
from backend.app.domain.calendars.scoring import compute_candidate_score
from backend.app.domain.calendars.types import (
    CandidateScore,
    GenerationSummary,
    SlotRequest,
    SlotResult,
)

# ---------------------------------------------------------------------------
# GenerationContext — input to the engine
# ---------------------------------------------------------------------------


@dataclass
class GenerationContext:
    """All data needed to generate one calendar month. Pre-loaded by the service."""

    year: int
    month: int
    # All service-active doctors with their data
    doctors: list  # list of DoctorModel
    # Allowed area IDs per doctor: {doctor_id: [area_id, ...]}
    allowed_areas: dict[str, list[str]]
    # Availability records per doctor: {doctor_id: [DoctorAvailabilityModel, ...]}
    availability: dict[str, list]
    # Active restriction records per doctor: {doctor_id: [DoctorRestrictionModel, ...]}
    restrictions: dict[str, list]
    # Assignments already in this version (starts empty): list of dicts with keys
    # doctor_id, service_date, service_area_id
    existing_assignments: list[dict]
    # Historical assignments (last 60 days): same dict format
    historical_assignments: list[dict]
    # Mission assignments (last 60 days): list of dicts with doctor_id, mission_date
    mission_assignments: list[dict]
    # Required service areas (ordered): ["emergencia", "pista", "disponible"]
    required_areas: list[str]
    # Area weights: {"emergencia": 3.0, "pista": 2.0, "disponible": 1.0}
    area_weights: dict[str, float]
    # Monthly service target per doctor: {doctor_id: int}. Default 3.
    monthly_service_targets: dict[str, int] | None = None
    # Monthly service max per doctor: {doctor_id: int}. Default 3.
    monthly_service_maxes: dict[str, int] | None = None
    # Pattern violations tracker (fairness): {doctor_id: count}. Reset per month.
    # Used by PatternRule to prefer doctors with fewer prior violations.
    pattern_violations: dict[str, int] | None = None


# ---------------------------------------------------------------------------
# CalendarEngine
# ---------------------------------------------------------------------------


class CalendarEngine:
    """Generates a full month's assignment schedule from a GenerationContext."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self, ctx: GenerationContext) -> GenerationSummary:
        """Generate calendar using CP-SAT optimizer.

        Delegates to OrToolsEngine for global optimal solution.
        """
        engine = OrToolsEngine()
        return engine.solve(ctx)

    # ------------------------------------------------------------------
    # Hard-filter: eligible doctors for a slot
    # ------------------------------------------------------------------

    def get_eligible_doctors(
        self,
        slot: SlotRequest,
        ctx: GenerationContext,
        current_assignments: list[dict],
    ) -> list:
        """Return the subset of ctx.doctors that are eligible for *slot*.

        A doctor is eligible iff ALL of the following hold:

        1. ``doctor.active`` and ``doctor.service_active`` are both True.
        2. ``slot.service_area_id`` is in the doctor's allowed areas.
        3. No active hard-block restriction covers ``slot.date``.
        4. The doctor has valid availability for ``slot.date``.
        5. The doctor has not already been assigned for ``slot.date`` in
           *current_assignments* (one assignment per calendar day).
        """
        # Dates already assigned per doctor in the current build pass.
        assigned_dates_by_doctor: dict[str, set[date]] = {}
        for assignment in current_assignments:
            d_id = assignment["doctor_id"]
            assigned_dates_by_doctor.setdefault(d_id, set()).add(
                assignment["service_date"]
            )

        eligible = []
        for doctor in ctx.doctors:
            # 1. Active status
            if not doctor.active or not doctor.service_active:
                continue

            # 2. Allowed service area
            allowed = ctx.allowed_areas.get(doctor.id, [])
            if slot.service_area_id not in allowed:
                continue

            # 3. No active hard-block restriction covering slot.date
            if self._has_hard_block(doctor.id, slot.date, ctx):
                continue

            # 4. Availability
            if not self._has_availability(doctor.id, slot.date, ctx):
                continue

            # 5. Not already assigned on this date
            if slot.date in assigned_dates_by_doctor.get(doctor.id, set()):
                continue

            # 6. Monthly maximum check (skip if not configured)
            monthly_max = ctx.monthly_service_maxes.get(doctor.id, 3) if ctx.monthly_service_maxes else 3
            monthly_count_so_far = sum(
                1 for a in current_assignments
                if a["doctor_id"] == doctor.id
                and _belongs_to_calendar_month(a["service_date"], ctx.year, ctx.month)
            )
            if monthly_count_so_far >= monthly_max:
                continue

            eligible.append(doctor)

        return eligible

    # ------------------------------------------------------------------
    # Hard-block restriction check
    # ------------------------------------------------------------------

    def _has_hard_block(
        self, doctor_id: str, target_date: date, ctx: GenerationContext
    ) -> bool:
        """Return True if the doctor has an active hard-block covering target_date."""
        restrictions = ctx.restrictions.get(doctor_id, [])
        for restriction in restrictions:
            if restriction.severity != "hard_block":
                continue
            # Only consider non-lifted restrictions
            starts = restriction.starts_at
            ends = restriction.ends_at  # may be None → open-ended

            # starts_at can be a date or datetime; normalise to date
            if hasattr(starts, "date"):
                starts = starts.date()

            if ends is not None and hasattr(ends, "date"):
                ends = ends.date()

            if target_date < starts:
                continue
            if ends is not None and target_date > ends:
                continue

            # Restriction covers this date and is a hard_block
            return True

        return False

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    def _has_availability(
        self, doctor_id: str, target_date: date, ctx: GenerationContext
    ) -> bool:
        """Return True if *doctor_id* is available on *target_date*.

        Rules
        -----
        - No records at all → True (unsubmitted = not blocked in MVP).
        - ``monthly_variable`` record: matches when month/year align and
          target_date.day is in available_days (or available_dates).
        - ``weekly_fixed`` record: matches when target_date.weekday() is in
          days_of_week.
        - ``recurring`` record: matches when target_date is the configured
          nth weekday of its month.
        - Either record type must also be within its effective date range
          (None boundaries are treated as unbounded).
        - If records exist but none match → False.
        """
        records = ctx.availability.get(doctor_id, [])

        if not records:
            # No availability submitted → treat as available (MVP behaviour)
            return True

        for record in records:
            availability_type = record.availability_type

            # Check effective date range first (applies to both types)
            effective_from = getattr(record, "effective_from", None)
            effective_to = getattr(record, "effective_to", None)

            if effective_from is not None:
                # Normalise datetime → date if needed
                eff_from = effective_from.date() if hasattr(effective_from, "date") else effective_from
                if target_date < eff_from:
                    continue

            if effective_to is not None:
                eff_to = effective_to.date() if hasattr(effective_to, "date") else effective_to
                if target_date > eff_to:
                    continue

            if availability_type == "monthly_variable":
                rec_month = getattr(record, "month", None)
                rec_year = getattr(record, "year", None)
                if rec_month != target_date.month or rec_year != target_date.year:
                    continue
                # Support both field names: available_days (spec) and available_dates (model)
                available_days = (
                    getattr(record, "available_days", None)
                    or getattr(record, "available_dates", None)
                    or []
                )
                if available_days is None:
                    available_days = []
                if target_date.day in available_days:
                    return True

            elif availability_type == "weekly_fixed":
                days_of_week = getattr(record, "days_of_week", None) or []
                if days_of_week is None:
                    days_of_week = []
                if target_date.weekday() in days_of_week:
                    return True

            elif availability_type == "recurring":
                if matches_recurring_monthly_rule(
                    target_date,
                    getattr(record, "weekday", None),
                    getattr(record, "week_number", None),
                ):
                    return True

            # Unknown availability_type → skip (fail safe)

        # Records exist but none matched
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _belongs_to_calendar_month(d: date, year: int, month: int) -> bool:
    """Return True if *d* belongs to the calendar month by Sunday ownership."""
    sunday = d + timedelta(days=6 - d.weekday())
    return sunday.year == year and sunday.month == month
