import types
from datetime import UTC, date

from backend.app.domain.doctors.eligibility import (
    AllowedServiceAreaSpec,
    AvailabilitySpec,
    EligibilityChecker,
    InactiveDoctorSpec,
    NoActiveHardBlockSpec,
)


def make_doctor(**kwargs):
    defaults = dict(
        id="doc-1",
        name="Dr Test",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="monthly",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_restriction(**kwargs):
    defaults = dict(
        id="r-1",
        severity="hard_block",
        restriction_type="license",
        description="Medical leave",
        lifted_at=None,
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_weekly_avail(days_of_week: list[int], effective_from=None, effective_to=None):
    return types.SimpleNamespace(
        availability_type="weekly_fixed",
        days_of_week=days_of_week,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def make_monthly_avail(year: int, month: int, available_dates: list[int]):
    return types.SimpleNamespace(
        availability_type="monthly_variable",
        year=year,
        month=month,
        available_dates=available_dates,
    )


# --- InactiveDoctorSpec ---


def test_inactive_doctor_block_when_active_false() -> None:
    doctor = make_doctor(active=False)
    result = InactiveDoctorSpec().check(doctor)
    assert result.passed is False
    assert result.code == "doctor_inactive"


def test_inactive_doctor_block_when_service_active_false() -> None:
    doctor = make_doctor(service_active=False)
    result = InactiveDoctorSpec().check(doctor)
    assert result.passed is False
    assert result.code == "doctor_inactive"


def test_active_doctor_passes() -> None:
    doctor = make_doctor()
    result = InactiveDoctorSpec().check(doctor)
    assert result.passed is True
    assert result.code == "doctor_active"


# --- AllowedServiceAreaSpec ---


def test_allowed_service_area_passes_when_area_in_list() -> None:
    doctor = make_doctor()
    result = AllowedServiceAreaSpec().check(doctor, "area-A", ["area-A", "area-B"])
    assert result.passed is True
    assert result.code == "area_allowed"


def test_allowed_service_area_fails_when_area_not_in_list() -> None:
    doctor = make_doctor()
    result = AllowedServiceAreaSpec().check(doctor, "area-C", ["area-A", "area-B"])
    assert result.passed is False
    assert result.code == "area_not_allowed"


def test_allowed_service_area_fails_when_list_is_empty() -> None:
    doctor = make_doctor()
    result = AllowedServiceAreaSpec().check(doctor, "area-A", [])
    assert result.passed is False
    assert result.code == "area_not_allowed"


# --- NoActiveHardBlockSpec ---


def test_hard_block_restriction_fails_when_active() -> None:
    doctor = make_doctor()
    restriction = make_restriction(severity="hard_block", lifted_at=None)
    result = NoActiveHardBlockSpec().check(doctor, [restriction], date(2026, 4, 29))
    assert result.passed is False
    assert result.code == "has_hard_block"


def test_hard_block_passes_when_restriction_is_lifted() -> None:
    from datetime import datetime

    doctor = make_doctor()
    restriction = make_restriction(
        severity="hard_block", lifted_at=datetime(2026, 4, 1, tzinfo=UTC)
    )
    result = NoActiveHardBlockSpec().check(doctor, [restriction], date(2026, 4, 29))
    assert result.passed is True
    assert result.code == "no_hard_block"


def test_hard_block_passes_when_no_restrictions() -> None:
    doctor = make_doctor()
    result = NoActiveHardBlockSpec().check(doctor, [], date(2026, 4, 29))
    assert result.passed is True
    assert result.code == "no_hard_block"


def test_non_hard_block_severity_does_not_fail() -> None:
    doctor = make_doctor()
    restriction = make_restriction(severity="soft_block", lifted_at=None)
    result = NoActiveHardBlockSpec().check(doctor, [restriction], date(2026, 4, 29))
    assert result.passed is True
    assert result.code == "no_hard_block"


# --- AvailabilitySpec (fixed mode) ---


def test_fixed_availability_passes_when_weekday_matches() -> None:
    # date(2026, 4, 27) is a Monday = weekday 0
    doctor = make_doctor(availability_mode="fixed")
    avail = make_weekly_avail(days_of_week=[0, 2, 4])
    result = AvailabilitySpec().check(doctor, date(2026, 4, 27), [avail], [])
    assert result.passed is True
    assert result.code == "available"


def test_fixed_availability_fails_when_weekday_not_in_days_of_week() -> None:
    # date(2026, 4, 28) is a Tuesday = weekday 1; record only covers Mon/Wed/Fri
    doctor = make_doctor(availability_mode="fixed")
    avail = make_weekly_avail(days_of_week=[0, 2, 4])
    result = AvailabilitySpec().check(doctor, date(2026, 4, 28), [avail], [])
    assert result.passed is False
    assert result.code == "not_available"


def test_fixed_availability_fails_when_no_weekly_records() -> None:
    doctor = make_doctor(availability_mode="fixed")
    result = AvailabilitySpec().check(doctor, date(2026, 4, 27), [], [])
    assert result.passed is False
    assert result.code == "not_available"


def test_fixed_availability_respects_effective_from() -> None:
    # Record is only effective from May 1; target date is April 27
    doctor = make_doctor(availability_mode="fixed")
    avail = make_weekly_avail(days_of_week=[0], effective_from=date(2026, 5, 1))
    result = AvailabilitySpec().check(doctor, date(2026, 4, 27), [avail], [])
    assert result.passed is False


def test_fixed_availability_respects_effective_to() -> None:
    # Record expired on April 1; target date is April 27
    doctor = make_doctor(availability_mode="fixed")
    avail = make_weekly_avail(days_of_week=[0], effective_to=date(2026, 4, 1))
    result = AvailabilitySpec().check(doctor, date(2026, 4, 27), [avail], [])
    assert result.passed is False


# --- AvailabilitySpec (monthly mode) ---


def test_monthly_availability_passes_when_day_in_available_dates() -> None:
    doctor = make_doctor(availability_mode="monthly")
    avail = make_monthly_avail(2026, 4, [10, 15, 29])
    result = AvailabilitySpec().check(doctor, date(2026, 4, 29), [], [avail])
    assert result.passed is True
    assert result.code == "available"


def test_monthly_availability_fails_when_day_not_in_available_dates() -> None:
    doctor = make_doctor(availability_mode="monthly")
    avail = make_monthly_avail(2026, 4, [10, 15])
    result = AvailabilitySpec().check(doctor, date(2026, 4, 29), [], [avail])
    assert result.passed is False
    assert result.code == "not_available"


def test_monthly_availability_passes_when_no_records_submitted() -> None:
    # Empty monthly_availability list means the doctor has not submitted yet;
    # the spec treats this as passed (handled by the pending-availability check instead).
    doctor = make_doctor(availability_mode="monthly")
    result = AvailabilitySpec().check(doctor, date(2026, 4, 29), [], [])
    assert result.passed is True
    assert result.code == "available"


# --- EligibilityChecker ---


def test_eligibility_checker_eligible_when_all_specs_pass() -> None:
    doctor = make_doctor(availability_mode="monthly")
    avail = make_monthly_avail(2026, 4, [29])
    report = EligibilityChecker().check(
        doctor,
        service_area_id="area-A",
        target_date=date(2026, 4, 29),
        allowed_area_ids=["area-A"],
        active_restrictions=[],
        weekly_availability=[],
        monthly_availability=[avail],
    )
    assert report.eligible is True
    assert report.blockers == []


def test_eligibility_checker_blocked_when_one_spec_fails() -> None:
    # Doctor is not service-active — InactiveDoctorSpec should fail.
    doctor = make_doctor(service_active=False, availability_mode="monthly")
    avail = make_monthly_avail(2026, 4, [29])
    report = EligibilityChecker().check(
        doctor,
        service_area_id="area-A",
        target_date=date(2026, 4, 29),
        allowed_area_ids=["area-A"],
        active_restrictions=[],
        weekly_availability=[],
        monthly_availability=[avail],
    )
    assert report.eligible is False
    assert len(report.blockers) >= 1
    assert any(b.code == "doctor_inactive" for b in report.blockers)


def test_eligibility_checker_blocked_by_hard_block() -> None:
    doctor = make_doctor(availability_mode="monthly")
    restriction = make_restriction(severity="hard_block", lifted_at=None)
    avail = make_monthly_avail(2026, 4, [29])
    report = EligibilityChecker().check(
        doctor,
        service_area_id="area-A",
        target_date=date(2026, 4, 29),
        allowed_area_ids=["area-A"],
        active_restrictions=[restriction],
        weekly_availability=[],
        monthly_availability=[avail],
    )
    assert report.eligible is False
    assert any(b.code == "has_hard_block" for b in report.blockers)


def test_eligibility_checker_blocked_by_area_not_allowed() -> None:
    doctor = make_doctor(availability_mode="monthly")
    avail = make_monthly_avail(2026, 4, [29])
    report = EligibilityChecker().check(
        doctor,
        service_area_id="area-Z",
        target_date=date(2026, 4, 29),
        allowed_area_ids=["area-A"],
        active_restrictions=[],
        weekly_availability=[],
        monthly_availability=[avail],
    )
    assert report.eligible is False
    assert any(b.code == "area_not_allowed" for b in report.blockers)


def test_eligibility_checker_returns_four_results() -> None:
    doctor = make_doctor(availability_mode="monthly")
    report = EligibilityChecker().check(
        doctor,
        service_area_id="area-A",
        target_date=date(2026, 4, 29),
        allowed_area_ids=["area-A"],
        active_restrictions=[],
        weekly_availability=[],
        monthly_availability=[],
    )
    assert len(report.results) == 4
