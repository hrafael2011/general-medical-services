import datetime
from uuid import uuid4

import pytest

from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.db.models.calendars import CalendarModel, CalendarVersionModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AREA_ID = "area-emergencia"


def _make_assignment_service(db_session) -> AssignmentService:
    return AssignmentService(
        CalendarRepository(db_session),
        DoctorRepository(db_session),
        AvailabilityRepository(db_session),
    )


def _create_doctor(db_session, *, active: bool = True, service_active: bool = True):
    """Create a doctor via DoctorService and optionally add allowed area."""
    doctor_svc = DoctorService(DoctorRepository(db_session))
    doctor = doctor_svc.create_doctor(
        actor_id="actor-001",
        name="Dr. Test",
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        # monthly mode with no submitted records passes AvailabilitySpec
        availability_mode="monthly",
        allowed_area_ids=[_AREA_ID],
    )
    if not active:
        doctor.active = False
        db_session.flush()
    if not service_active:
        doctor.service_active = False
        db_session.flush()
    return doctor


def _create_calendar_and_version(db_session) -> tuple[CalendarModel, CalendarVersionModel]:
    """Create a CalendarModel + CalendarVersionModel directly and return both."""
    now = datetime.datetime.now(datetime.UTC)
    calendar = CalendarModel(
        id=str(uuid4()),
        year=2026,
        month=5,
        status="draft",
        generation_mode="manual",
        created_by="actor-001",
        approved_by=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
    )
    db_session.add(calendar)
    db_session.flush()

    version = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status="draft",
        created_by="actor-001",
        reason=None,
        created_at=now,
    )
    db_session.add(version)
    db_session.flush()

    return calendar, version


# ---------------------------------------------------------------------------
# test_assign_doctor_to_slot
# ---------------------------------------------------------------------------


def test_assign_doctor_to_slot(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    service = _make_assignment_service(db_session)

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    assert assignment.id is not None
    assert assignment.doctor_id == doctor.id
    assert assignment.calendar_version_id == version.id
    assert assignment.service_area_id == _AREA_ID
    assert assignment.service_date == datetime.date(2026, 5, 15)


# ---------------------------------------------------------------------------
# test_assign_to_approved_version_raises
# ---------------------------------------------------------------------------


def test_assign_to_approved_version_raises(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    service = _make_assignment_service(db_session)

    # Approve the version directly
    version.status = "approved"
    db_session.flush()

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 15),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "version_is_approved"


# ---------------------------------------------------------------------------
# test_remove_assignment
# ---------------------------------------------------------------------------


def test_remove_assignment(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    service = _make_assignment_service(db_session)
    cal_repo = CalendarRepository(db_session)

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )
    assignment_id = assignment.id

    service.remove_assignment(actor_id="actor-001", assignment_id=assignment_id)

    assert cal_repo.get_assignment_by_id(assignment_id) is None


# ---------------------------------------------------------------------------
# test_replace_assignment
# ---------------------------------------------------------------------------


def test_replace_assignment(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor_a = _create_doctor(db_session)

    # Create second doctor with same allowed area
    doctor_svc = DoctorService(DoctorRepository(db_session))
    doctor_b = doctor_svc.create_doctor(
        actor_id="actor-001",
        name="Dr. B",
        sex="female",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        allowed_area_ids=[_AREA_ID],
    )

    service = _make_assignment_service(db_session)

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor_a.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )
    assert assignment.doctor_id == doctor_a.id

    updated = service.replace_assignment(
        actor_id="actor-001",
        assignment_id=assignment.id,
        new_doctor_id=doctor_b.id,
    )

    assert updated.doctor_id == doctor_b.id


# ---------------------------------------------------------------------------
# test_hard_block_prevents_assignment
# ---------------------------------------------------------------------------


def test_hard_block_prevents_assignment(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    # active=False triggers InactiveDoctorSpec → code "doctor_inactive" → hard block
    doctor = _create_doctor(db_session, active=False)
    service = _make_assignment_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 15),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "hard_block"


def test_soft_warning_requires_justification_and_is_stored(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor_svc = DoctorService(DoctorRepository(db_session))
    doctor = doctor_svc.create_doctor(
        actor_id="actor-001",
        name="Dr. Fixed",
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="fixed",
        allowed_area_ids=[_AREA_ID],
    )
    service = _make_assignment_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 15),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "soft_warning"

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
        override_justification="Asignación manual autorizada por necesidad operativa.",
    )

    assert assignment.override_justification == "Asignación manual autorizada por necesidad operativa."
    assert assignment.rationale["manual_override_warnings"][0]["code"] == "not_available"
