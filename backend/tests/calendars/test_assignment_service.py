import datetime
from uuid import uuid4

import pytest

from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.db.models.calendars import (
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AREA_ID = "area-emergencia"
_SPACING_WARNING = "spacing < 14 días desde último turno fuerte"


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


def _create_week(
    db_session,
    calendar: CalendarModel,
    version: CalendarVersionModel,
    *,
    status: str,
) -> CalendarWeekModel:
    week = CalendarWeekModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        calendar_version_id=version.id,
        week_number=3,
        label="3RA SEMANA",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 17),
        status=status,
    )
    db_session.add(week)
    db_session.flush()
    return week


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


def test_assign_to_approved_week_raises(db_session) -> None:
    calendar, version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, version, status="approved")
    doctor = _create_doctor(db_session)
    service = _make_assignment_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 15),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "week_locked"


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


def test_remove_assignment_from_approved_week_raises(db_session) -> None:
    calendar, version = _create_calendar_and_version(db_session)
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
    _create_week(db_session, calendar, version, status="approved")

    with pytest.raises(CalendarServiceError) as exc_info:
        service.remove_assignment(actor_id="actor-001", assignment_id=assignment.id)

    assert exc_info.value.code == "week_locked"
    assert cal_repo.get_assignment_by_id(assignment.id) is not None


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


def test_replace_assignment_from_approved_week_raises(db_session) -> None:
    calendar, version = _create_calendar_and_version(db_session)
    doctor_a = _create_doctor(db_session)
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
    _create_week(db_session, calendar, version, status="approved")

    with pytest.raises(CalendarServiceError) as exc_info:
        service.replace_assignment(
            actor_id="actor-001",
            assignment_id=assignment.id,
            new_doctor_id=doctor_b.id,
        )

    assert exc_info.value.code == "week_locked"


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


def test_assign_doctor_respects_recurring_availability(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor_svc = DoctorService(DoctorRepository(db_session))
    doctor = doctor_svc.create_doctor(
        actor_id="actor-001",
        name="Dr. Recurring",
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=1,
        monthly_service_max=1,
        monthly_service_limit_mode="hard_limit",
        availability_mode="fixed",
        allowed_area_ids=[_AREA_ID],
    )
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(DoctorAvailabilityModel(
        id=str(uuid4()),
        doctor_id=doctor.id,
        availability_type="recurring",
        days_of_week=None,
        available_dates=None,
        weekday=4,
        week_number=-1,
        year=None,
        month=None,
        submitted_at=None,
        effective_from=None,
        effective_to=None,
        source="manual",
        review_status="approved",
        created_by="actor-001",
        created_at=now,
        updated_at=now,
    ))
    db_session.flush()

    service = _make_assignment_service(db_session)

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 29),
        service_area_id=_AREA_ID,
    )

    assert assignment.doctor_id == doctor.id

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 22),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "soft_warning"


def test_assign_doctor_warns_when_warn_only_monthly_max_is_reached(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 1
    doctor.monthly_service_limit_mode = "warn_only"
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 16),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "soft_warning"

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 16),
        service_area_id=_AREA_ID,
        force_warnings=["monthly_max_exceeded"],
    )
    assert assignment.rationale["overridden_warnings"] == ["monthly_max_exceeded"]


def test_assign_doctor_blocks_when_hard_limit_monthly_max_is_reached(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 1
    doctor.monthly_service_limit_mode = "hard_limit"
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 16),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "hard_block"


def test_assign_doctor_counts_monthly_max_by_operational_month(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 1
    doctor.monthly_service_limit_mode = "hard_limit"
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 4, 27),
        service_area_id=_AREA_ID,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 2),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "hard_block"


def test_evaluate_slot_reports_warn_only_monthly_max(db_session) -> None:
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 1
    doctor.monthly_service_limit_mode = "warn_only"
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 4, 27),
        service_area_id=_AREA_ID,
    )

    result = service.evaluate_slot(
        version_id=version.id,
        doctor_id=doctor.id,
        target_date=datetime.date(2026, 5, 2),
        service_area_id=_AREA_ID,
    )

    assert result["hard_blocks"] == []
    assert result["warnings"][0]["code"] == "monthly_max_exceeded"


def test_evaluate_slot_maps_service_area_uuid_for_spacing_warnings(db_session) -> None:
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(ServiceAreaModel(
        id=_AREA_ID,
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=now,
        updated_at=now,
    ))
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 999
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    result = service.evaluate_slot(
        version_id=version.id,
        doctor_id=doctor.id,
        target_date=datetime.date(2026, 5, 20),
        service_area_id=_AREA_ID,
    )

    assert result["hard_blocks"] == []
    assert any("14" in warning["code"] for warning in result["warnings"])


def test_assign_doctor_requires_spacing_warning_confirmation_when_called_directly(db_session) -> None:
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(ServiceAreaModel(
        id=_AREA_ID,
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=now,
        updated_at=now,
    ))
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 999
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 20),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "soft_warning"
    assert "14" in str(exc_info.value)

    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 20),
        service_area_id=_AREA_ID,
        force_warnings=[_SPACING_WARNING],
    )

    assert assignment.rationale["overridden_warnings"] == [_SPACING_WARNING]


def test_replace_assignment_requires_spacing_warning_confirmation_when_called_directly(db_session) -> None:
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(ServiceAreaModel(
        id=_AREA_ID,
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=now,
        updated_at=now,
    ))
    _calendar, version = _create_calendar_and_version(db_session)
    doctor_a = _create_doctor(db_session)
    doctor_b = DoctorService(DoctorRepository(db_session)).create_doctor(
        actor_id="actor-001",
        name="Dr. Spacing B",
        sex="female",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=999,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        allowed_area_ids=[_AREA_ID],
    )
    doctor_a.monthly_service_max = 999
    db_session.flush()
    service = _make_assignment_service(db_session)

    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor_b.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )
    assignment = service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor_a.id,
        date=datetime.date(2026, 5, 20),
        service_area_id=_AREA_ID,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.replace_assignment(
            actor_id="actor-001",
            assignment_id=assignment.id,
            new_doctor_id=doctor_b.id,
        )

    assert exc_info.value.code == "soft_warning"
    assert "14" in str(exc_info.value)

    updated = service.replace_assignment(
        actor_id="actor-001",
        assignment_id=assignment.id,
        new_doctor_id=doctor_b.id,
        force_warnings=[_SPACING_WARNING],
    )

    assert updated.doctor_id == doctor_b.id
    assert updated.rationale["overridden_warnings"] == [_SPACING_WARNING]


# ---------------------------------------------------------------------------
# test_assign_doctor_fails_when_area_not_allowed
# ---------------------------------------------------------------------------


def test_assign_doctor_fails_when_area_not_allowed(db_session) -> None:
    """Assigning to an area the doctor is not allowed in raises hard_block."""
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)  # Only allowed in _AREA_ID
    service = _make_assignment_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id=doctor.id,
            date=datetime.date(2026, 5, 15),
            service_area_id="area-pista",  # NOT in doctor's allowed areas
        )

    assert exc_info.value.code == "hard_block"


# ---------------------------------------------------------------------------
# test_assign_doctor_fails_when_service_inactive
# ---------------------------------------------------------------------------


def test_assign_doctor_fails_when_service_inactive(db_session) -> None:
    """service_active=False triggers hard_block."""
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session, service_active=False)
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


# ---------------------------------------------------------------------------
# test_assign_doctor_fails_when_doctor_not_found
# ---------------------------------------------------------------------------


def test_assign_doctor_fails_when_doctor_not_found(db_session) -> None:
    """Non-existent doctor_id raises doctor_not_found."""
    _calendar, version = _create_calendar_and_version(db_session)
    service = _make_assignment_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.assign_doctor(
            actor_id="actor-001",
            version_id=version.id,
            doctor_id="non-existent-doctor-id",
            date=datetime.date(2026, 5, 15),
            service_area_id=_AREA_ID,
        )

    assert exc_info.value.code == "doctor_not_found"


# ---------------------------------------------------------------------------
# test_evaluate_slot_reports_hard_blocks_for_inactive_doctor
# ---------------------------------------------------------------------------


def test_evaluate_slot_reports_hard_blocks_for_inactive_doctor(db_session) -> None:
    """evaluate_slot reports hard_blocks when doctor is inactive."""
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session, active=False)
    service = _make_assignment_service(db_session)

    result = service.evaluate_slot(
        version_id=version.id,
        doctor_id=doctor.id,
        target_date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )

    assert len(result["hard_blocks"]) > 0, (
        f"Expected hard_blocks for inactive doctor, got {result['hard_blocks']}"
    )


# ---------------------------------------------------------------------------
# test_evaluate_slot_reports_multiple_warnings
# ---------------------------------------------------------------------------


def test_evaluate_slot_reports_multiple_warnings(db_session) -> None:
    """evaluate_slot reports both spacing and monthly_max warnings together."""
    now = datetime.datetime.now(datetime.UTC)
    db_session.add(ServiceAreaModel(
        id=_AREA_ID,
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=now,
        updated_at=now,
    ))
    _calendar, version = _create_calendar_and_version(db_session)
    doctor = _create_doctor(db_session)
    doctor.monthly_service_max = 2
    doctor.monthly_service_limit_mode = "warn_only"
    db_session.flush()
    service = _make_assignment_service(db_session)

    # First assignment on May 15 (strong area) — creates spacing context
    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 15),
        service_area_id=_AREA_ID,
    )
    # Second assignment also triggers spacing warning (May 15→16 is <14 days)
    # AND reaches monthly max — force both
    service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor.id,
        date=datetime.date(2026, 5, 16),
        service_area_id=_AREA_ID,
        force_warnings=["monthly_max_exceeded", _SPACING_WARNING],
    )

    # Now evaluate for May 20 — should have both spacing (<14 days from strong)
    # and monthly_max warnings
    result = service.evaluate_slot(
        version_id=version.id,
        doctor_id=doctor.id,
        target_date=datetime.date(2026, 5, 20),
        service_area_id=_AREA_ID,
    )

    warning_codes = [w["code"] for w in result["warnings"]]
    assert len(warning_codes) >= 2, (
        f"Expected >=2 warnings (spacing + monthly_max), "
        f"got {len(warning_codes)}: {warning_codes}"
    )
