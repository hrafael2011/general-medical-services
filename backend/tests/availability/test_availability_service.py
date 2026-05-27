from datetime import date

import pytest

from backend.app.application.availability.errors import AvailabilityError
from backend.app.application.availability.service import AvailabilityService
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository


def make_availability_service(db_session) -> AvailabilityService:
    return AvailabilityService(
        availability_repo=AvailabilityRepository(db_session),
        doctor_repo=DoctorRepository(db_session),
    )


def make_doctor_service(db_session) -> DoctorService:
    return DoctorService(DoctorRepository(db_session))


def create_doctor(db_session, *, availability_mode="monthly", name="Dr Test", sex="male"):
    return make_doctor_service(db_session).create_doctor(
        actor_id="actor-1",
        name=name,
        sex=sex,
        rank_id=None,
        department_id=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode=availability_mode,
        allowed_area_ids=[],
    )


# --- set_weekly_availability ---


def test_set_weekly_availability_creates_record_for_fixed_mode_doctor(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="fixed")
    service = make_availability_service(db_session)

    record = service.set_weekly_availability(
        doctor.id,
        days_of_week=[0, 2, 4],
        actor_id="actor-1",
    )

    assert record.doctor_id == doctor.id
    assert record.availability_type == "weekly_fixed"
    assert sorted(record.days_of_week) == [0, 2, 4]


def test_set_weekly_availability_deduplicates_days(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="fixed")
    service = make_availability_service(db_session)

    record = service.set_weekly_availability(
        doctor.id,
        days_of_week=[1, 1, 3, 3],
        actor_id="actor-1",
    )

    assert sorted(record.days_of_week) == [1, 3]


def test_set_weekly_availability_replaces_existing_fixed_patterns(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="fixed")
    service = make_availability_service(db_session)
    availability_repo = AvailabilityRepository(db_session)

    service.set_recurring_availability(
        doctor.id,
        weekday=1,
        week_number=1,
        actor_id="actor-1",
    )
    service.set_weekly_availability(
        doctor.id,
        days_of_week=[0, 2],
        actor_id="actor-1",
    )

    records = availability_repo.list_availability_for_doctor(doctor.id)
    assert len(records) == 1
    assert records[0].availability_type == "weekly_fixed"
    assert sorted(records[0].days_of_week) == [0, 2]


def test_set_weekly_availability_fails_for_monthly_mode_doctor(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    with pytest.raises(AvailabilityError) as exc_info:
        service.set_weekly_availability(
            doctor.id,
            days_of_week=[0, 2],
            actor_id="actor-1",
        )

    assert exc_info.value.code == "mode_mismatch"


# --- set_monthly_availability ---


def test_set_monthly_availability_creates_record_for_monthly_mode_doctor(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    record = service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=4,
        available_dates=[5, 10, 15, 29],
        actor_id="actor-1",
    )

    assert record.doctor_id == doctor.id
    assert record.availability_type == "monthly_variable"
    assert record.year == 2026
    assert record.month == 4
    assert record.available_dates == [5, 10, 15, 29]


def test_set_monthly_availability_fails_for_fixed_mode_doctor(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="fixed")
    service = make_availability_service(db_session)

    with pytest.raises(AvailabilityError) as exc_info:
        service.set_monthly_availability(
            doctor.id,
            year=2026,
            month=4,
            available_dates=[5, 10],
            actor_id="actor-1",
        )

    assert exc_info.value.code == "mode_mismatch"


def test_set_monthly_availability_replaces_existing_record(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)
    availability_repo = AvailabilityRepository(db_session)

    service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=4,
        available_dates=[1, 2, 3],
        actor_id="actor-1",
    )
    service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=4,
        available_dates=[10, 20, 29],
        actor_id="actor-1",
    )

    records = availability_repo.list_monthly_variable_for_period(doctor.id, 2026, 4)
    assert len(records) == 1
    assert records[0].available_dates == [10, 20, 29]


def test_set_monthly_availability_deduplicates_and_sorts_dates(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    record = service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=5,
        available_dates=[15, 5, 15, 10],
        actor_id="actor-1",
    )

    assert record.available_dates == [5, 10, 15]


# --- set_recurring_availability ---


def test_set_recurring_availability_replaces_existing_fixed_patterns(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="fixed")
    service = make_availability_service(db_session)
    availability_repo = AvailabilityRepository(db_session)

    service.set_weekly_availability(
        doctor.id,
        days_of_week=[1],
        actor_id="actor-1",
    )
    service.set_recurring_availability(
        doctor.id,
        weekday=1,
        week_number=1,
        actor_id="actor-1",
    )

    records = availability_repo.list_availability_for_doctor(doctor.id)
    assert len(records) == 1
    assert records[0].availability_type == "recurring"
    assert records[0].weekday == 1
    assert records[0].week_number == 1


# --- has_submitted_monthly_availability ---


def test_has_submitted_monthly_availability_returns_false_when_no_record(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    result = service.has_submitted_monthly_availability(doctor.id, year=2026, month=4)

    assert result is False


def test_has_submitted_monthly_availability_returns_true_when_record_exists(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=4,
        available_dates=[10, 20],
        actor_id="actor-1",
    )

    result = service.has_submitted_monthly_availability(doctor.id, year=2026, month=4)

    assert result is True


def test_has_submitted_monthly_availability_is_period_specific(db_session) -> None:
    doctor = create_doctor(db_session, availability_mode="monthly")
    service = make_availability_service(db_session)

    service.set_monthly_availability(
        doctor.id,
        year=2026,
        month=3,
        available_dates=[1, 15],
        actor_id="actor-1",
    )

    # April has no record even though March does
    assert service.has_submitted_monthly_availability(doctor.id, year=2026, month=4) is False
    assert service.has_submitted_monthly_availability(doctor.id, year=2026, month=3) is True


# --- add_restriction ---


def test_add_restriction_creates_record_with_correct_fields(db_session) -> None:
    doctor = create_doctor(db_session)
    service = make_availability_service(db_session)

    restriction = service.add_restriction(
        doctor.id,
        restriction_type="license",
        severity="hard_block",
        starts_at=date(2026, 4, 1),
        ends_at=date(2026, 4, 30),
        description="Medical leave",
        reason_id=None,
        actor_id="actor-1",
    )

    assert restriction.doctor_id == doctor.id
    assert restriction.restriction_type == "license"
    assert restriction.severity == "hard_block"
    assert restriction.starts_at == date(2026, 4, 1)
    assert restriction.ends_at == date(2026, 4, 30)
    assert restriction.description == "Medical leave"
    assert restriction.lifted_at is None


def test_add_restriction_fails_for_unknown_doctor(db_session) -> None:
    service = make_availability_service(db_session)

    with pytest.raises(AvailabilityError) as exc_info:
        service.add_restriction(
            "non-existent-id",
            restriction_type="license",
            severity="hard_block",
            starts_at=date(2026, 4, 1),
            ends_at=None,
            description=None,
            reason_id=None,
            actor_id="actor-1",
        )

    assert exc_info.value.code == "doctor_not_found"


# --- lift_restriction ---


def test_lift_restriction_sets_lifted_at(db_session) -> None:
    doctor = create_doctor(db_session)
    service = make_availability_service(db_session)

    restriction = service.add_restriction(
        doctor.id,
        restriction_type="license",
        severity="hard_block",
        starts_at=date(2026, 4, 1),
        ends_at=None,
        description="Leave",
        reason_id=None,
        actor_id="actor-1",
    )
    assert restriction.lifted_at is None

    lifted = service.lift_restriction(restriction.id, actor_id="actor-1")

    assert lifted.lifted_at is not None
    assert lifted.lifted_by == "actor-1"


def test_lift_restriction_fails_for_unknown_restriction(db_session) -> None:
    service = make_availability_service(db_session)

    with pytest.raises(AvailabilityError) as exc_info:
        service.lift_restriction("non-existent-restriction-id", actor_id="actor-1")

    assert exc_info.value.code == "restriction_not_found"


# --- missing availability exclusion check ---


def test_missing_availability_exclusion_finds_monthly_doctors_without_submitted_availability(
    db_session,
) -> None:
    make_doctor_service(db_session)
    avail_svc = make_availability_service(db_session)
    doctor_repo = DoctorRepository(db_session)

    # Two monthly-mode doctors and one fixed-mode doctor
    doc_monthly_submitted = create_doctor(
        db_session, availability_mode="monthly", name="Dr Submitted"
    )
    create_doctor(
        db_session, availability_mode="monthly", name="Dr Pending"
    )
    _doc_fixed = create_doctor(db_session, availability_mode="fixed", name="Dr Fixed")

    # Only the first monthly doctor has submitted availability for April 2026
    avail_svc.set_monthly_availability(
        doc_monthly_submitted.id,
        year=2026,
        month=4,
        available_dates=[10, 20],
        actor_id="actor-1",
    )

    # Replicate the pending-availability logic from the route
    all_active = doctor_repo.list_service_active()
    monthly_doctors = [d for d in all_active if d.availability_mode == "monthly"]
    pending = [
        d
        for d in monthly_doctors
        if not avail_svc.has_submitted_monthly_availability(d.id, year=2026, month=4)
    ]

    pending_names = [d.name for d in pending]
    assert "Dr Pending" in pending_names
    assert "Dr Submitted" not in pending_names
    assert "Dr Fixed" not in pending_names


def test_missing_availability_exclusion_returns_empty_when_all_submitted(db_session) -> None:
    avail_svc = make_availability_service(db_session)
    doctor_repo = DoctorRepository(db_session)

    doc1 = create_doctor(db_session, availability_mode="monthly", name="Dr Alpha")
    doc2 = create_doctor(db_session, availability_mode="monthly", name="Dr Beta")

    avail_svc.set_monthly_availability(
        doc1.id, year=2026, month=4, available_dates=[5], actor_id="actor-1"
    )
    avail_svc.set_monthly_availability(
        doc2.id, year=2026, month=4, available_dates=[6], actor_id="actor-1"
    )

    all_active = doctor_repo.list_service_active()
    monthly_doctors = [d for d in all_active if d.availability_mode == "monthly"]
    pending = [
        d
        for d in monthly_doctors
        if not avail_svc.has_submitted_monthly_availability(d.id, year=2026, month=4)
    ]

    assert pending == []
