from dataclasses import dataclass, field
from datetime import date

from backend.app.domain.availability_rules import matches_recurring_monthly_rule


@dataclass
class EligibilityResult:
    passed: bool
    code: str
    reason: str


@dataclass
class EligibilityReport:
    eligible: bool
    results: list[EligibilityResult] = field(default_factory=list)

    @property
    def blockers(self) -> list[EligibilityResult]:
        return [r for r in self.results if not r.passed]

    @property
    def warnings(self) -> list[EligibilityResult]:
        return [r for r in self.results if not r.passed]


class InactiveDoctorSpec:
    """Checks that both doctor.active and doctor.service_active are True."""

    def check(self, doctor) -> EligibilityResult:
        if not doctor.active:
            return EligibilityResult(
                passed=False,
                code="doctor_inactive",
                reason=f"Doctor '{doctor.name}' is not active (active=False).",
            )
        if not doctor.service_active:
            return EligibilityResult(
                passed=False,
                code="doctor_inactive",
                reason=f"Doctor '{doctor.name}' is not service-active (service_active=False).",
            )
        return EligibilityResult(
            passed=True,
            code="doctor_active",
            reason=f"Doctor '{doctor.name}' is active and service-active.",
        )


class AllowedServiceAreaSpec:
    """Checks that the requested service area is in the doctor's allowed area list."""

    def check(
        self, doctor, service_area_id: str, allowed_area_ids: list[str]
    ) -> EligibilityResult:
        if service_area_id in allowed_area_ids:
            return EligibilityResult(
                passed=True,
                code="area_allowed",
                reason=f"Service area '{service_area_id}' is allowed for doctor '{doctor.name}'.",
            )
        return EligibilityResult(
            passed=False,
            code="area_not_allowed",
            reason=(
                f"Service area '{service_area_id}' is not in the allowed areas "
                f"for doctor '{doctor.name}'."
            ),
        )


class NoActiveHardBlockSpec:
    """Checks that no active hard-block restriction covers the given date."""

    def check(self, doctor, restrictions: list, on_date: date) -> EligibilityResult:
        for restriction in restrictions:
            if restriction.severity == "hard_block" and restriction.lifted_at is None:
                detail = restriction.description or restriction.restriction_type
                return EligibilityResult(
                    passed=False,
                    code="has_hard_block",
                    reason=(
                        f"Doctor '{doctor.name}' has an active hard block on {on_date}: "
                        f"{detail}."
                    ),
                )
        return EligibilityResult(
            passed=True,
            code="no_hard_block",
            reason=f"No active hard-block restrictions found for doctor '{doctor.name}' on {on_date}.",
        )


class AvailabilitySpec:
    """
    Checks whether the doctor has declared availability on a specific date,
    according to their availability_mode ('fixed' or 'monthly').
    """

    def check(
        self,
        doctor,
        target_date: date,
        weekly_availability: list,
        monthly_availability: list,
    ) -> EligibilityResult:
        mode = doctor.availability_mode

        if mode == "fixed":
            weekday = target_date.weekday()  # Monday=0
            for record in weekly_availability:
                if record.availability_type == "weekly_fixed":
                    days = record.days_of_week or []
                    if weekday not in days:
                        continue
                elif record.availability_type == "recurring":
                    if not matches_recurring_monthly_rule(
                        target_date,
                        record.weekday,
                        record.week_number,
                    ):
                        continue
                else:
                    continue
                # Respect effective_from / effective_to when set
                if record.effective_from and target_date < record.effective_from:
                    continue
                if record.effective_to and target_date > record.effective_to:
                    continue
                return EligibilityResult(
                    passed=True,
                    code="available",
                    reason=(
                        f"Doctor '{doctor.name}' has an availability record "
                        f"covering weekday {weekday} on {target_date}."
                    ),
                )
            return EligibilityResult(
                passed=False,
                code="not_available",
                reason=(
                    f"Doctor '{doctor.name}' (mode=fixed) has no fixed availability "
                    f"record that covers weekday {weekday} on {target_date}."
                ),
            )

        if mode == "monthly":
            if not monthly_availability:
                # No records submitted for this period — treat as unsubmitted, not blocked
                return EligibilityResult(
                    passed=True,
                    code="available",
                    reason=(
                        f"Doctor '{doctor.name}' (mode=monthly) has not submitted availability "
                        f"for the period containing {target_date}; "
                        "exclusion from generation is handled by the pending-availability check."
                    ),
                )
            day = target_date.day
            for record in monthly_availability:
                if record.availability_type != "monthly_variable":
                    continue
                dates = record.available_dates or []
                if day in dates:
                    return EligibilityResult(
                        passed=True,
                        code="available",
                        reason=(
                            f"Doctor '{doctor.name}' (mode=monthly) declared availability "
                            f"on day {day} of the month ({target_date})."
                        ),
                    )
            return EligibilityResult(
                passed=False,
                code="not_available",
                reason=(
                    f"Doctor '{doctor.name}' (mode=monthly) did not include day {target_date.day} "
                    f"in their available dates for {target_date.strftime('%Y-%m')}."
                ),
            )

        # Unknown mode — fail safe
        return EligibilityResult(
            passed=False,
            code="not_available",
            reason=(
                f"Doctor '{doctor.name}' has an unrecognised availability_mode '{mode}'; "
                "cannot determine availability."
            ),
        )


class EligibilityChecker:
    """
    Runs all eligibility specs for a doctor on a given date and service area.
    Returns a consolidated EligibilityReport.
    """

    def check(
        self,
        doctor,
        *,
        service_area_id: str,
        target_date: date,
        allowed_area_ids: list[str],
        active_restrictions: list,
        weekly_availability: list,
        monthly_availability: list,
    ) -> EligibilityReport:
        results = [
            InactiveDoctorSpec().check(doctor),
            AllowedServiceAreaSpec().check(doctor, service_area_id, allowed_area_ids),
            NoActiveHardBlockSpec().check(doctor, active_restrictions, target_date),
            AvailabilitySpec().check(
                doctor, target_date, weekly_availability, monthly_availability
            ),
        ]
        eligible = all(r.passed for r in results)
        return EligibilityReport(eligible=eligible, results=results)
