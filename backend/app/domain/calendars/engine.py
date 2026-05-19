"""
Calendar generation engine.

Pure domain logic: no SQLAlchemy, no repository calls, no DB access.
All data is pre-loaded by the service layer and passed in via GenerationContext.
"""

import calendar as cal_module
from dataclasses import dataclass
from datetime import date, timedelta

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


# ---------------------------------------------------------------------------
# CalendarEngine
# ---------------------------------------------------------------------------


class CalendarEngine:
    """Generates a full month's assignment schedule from a GenerationContext."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self, ctx: GenerationContext) -> GenerationSummary:
        """Generate all slot assignments for the month described in *ctx*.

        Returns a :class:`GenerationSummary` with every slot result (assigned
        or gap).  version_id and calendar_id are left as empty strings because
        those identifiers are assigned by the service layer, not the engine.
        """

        # 1. Build all slots: one per (day, area) combination across ALL weeks
        #    that belong to this month (including cross-boundary days).
        from backend.app.domain.calendars.weeks import compute_weeks

        weeks = compute_weeks(ctx.year, ctx.month)
        date_set: set[date] = set()
        for w in weeks:
            _, _, sy, sm, sd, ey, em, ed = w
            d = date(sy, sm, sd)
            end = date(ey, em, ed)
            while d <= end:
                date_set.add(d)
                d += timedelta(days=1)

        all_slots: list[SlotRequest] = [
            SlotRequest(
                date=d,
                service_area_id=area,
                area_weight=ctx.area_weights.get(area, 1.0),
            )
            for d in sorted(date_set)
            for area in ctx.required_areas
        ]

        # 2. Sort slots by constraint level (most constrained first).
        #    We count eligible doctors using an empty current-assignments list
        #    so that the sort order is deterministic and independent of
        #    insertion order.
        def _eligible_count(slot: SlotRequest) -> int:
            return len(self.get_eligible_doctors(slot, ctx, []))

        sorted_slots = sorted(all_slots, key=_eligible_count)

        # 3. Fill slots in sorted order, accumulating assignments as we go.
        current_assignments: list[dict] = list(ctx.existing_assignments)
        slot_results: list[SlotResult] = []

        for slot in sorted_slots:
            eligible = self.get_eligible_doctors(slot, ctx, current_assignments)

            if not eligible:
                slot_results.append(
                    SlotResult(
                        slot=slot,
                        assigned_doctor_id=None,
                        score=None,
                        rationale={"gap": True, "reason": "no_eligible_candidates"},
                    )
                )
                continue

            # Score each eligible doctor; combine monthly + historical data.
            monthly_assignments = [
                a for a in current_assignments
                if _belongs_to_calendar_month(a["service_date"], ctx.year, ctx.month)
            ]

            scores: list[CandidateScore] = [
                compute_candidate_score(
                    doctor_id=doctor.id,
                    slot=slot,
                    monthly_assignments=monthly_assignments,
                    historical_assignments=ctx.historical_assignments,
                    mission_assignments=ctx.mission_assignments,
                    monthly_service_target=ctx.monthly_service_targets.get(doctor.id, 3)
                    if ctx.monthly_service_targets else 3,
                )
                for doctor in eligible
            ]

            # Pick the highest score; break ties alphabetically by doctor_id.
            scores.sort(key=lambda s: (-s.score, s.doctor_id))
            best = scores[0]

            rationale = {
                "source": "generated",
                "score": best.score,
                "monthly_load": best.monthly_load,
                "historical_load": best.historical_load,
                "days_since_last": best.days_since_last,
                "days_since_strong": best.days_since_strong,
                "monthly_count": best.monthly_count,
                "warnings": best.warnings,
            }

            slot_results.append(
                SlotResult(
                    slot=slot,
                    assigned_doctor_id=best.doctor_id,
                    score=best,
                    rationale=rationale,
                )
            )

            # Record the new assignment so subsequent slots see it.
            current_assignments.append(
                {
                    "doctor_id": best.doctor_id,
                    "service_date": slot.date,
                    "service_area_id": slot.service_area_id,
                }
            )

        # 4. Build summary
        assigned_count = sum(
            1 for r in slot_results if r.assigned_doctor_id is not None
        )
        gap_count = len(slot_results) - assigned_count

        return GenerationSummary(
            version_id="",
            calendar_id="",
            month=ctx.month,
            year=ctx.year,
            total_slots=len(slot_results),
            assigned_count=assigned_count,
            gap_count=gap_count,
            slot_results=slot_results,
        )

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
