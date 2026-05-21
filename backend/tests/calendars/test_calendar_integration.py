"""End-to-end integration tests: Generate → Manual Adjust → Verify.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import datetime
from uuid import uuid4

from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.infrastructure.db.models.calendars import (
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import (
    DoctorAllowedAreaModel,
    DoctorModel,
)
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

# ---------------------------------------------------------------------------
# Fixed area IDs
# ---------------------------------------------------------------------------

_AREA_EMERGENCIA = "emergencia"
_AREA_PISTA = "pista"
_AREA_DISPONIBLE = "disponible"

_YEAR = 2026
_MONTH = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_service_areas(db_session) -> None:
    now = datetime.datetime.now(datetime.UTC)
    for area_id, name, weight in [
        (_AREA_EMERGENCIA, "Emergencia", 3),
        (_AREA_PISTA, "Pista", 2),
        (_AREA_DISPONIBLE, "Disponible", 1),
    ]:
        db_session.add(
            ServiceAreaModel(
                id=area_id,
                code=area_id,
                display_name=name,
                active=True,
                required_for_daily_coverage=True,
                load_weight=weight,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.flush()


def _create_calendar_and_version(db_session) -> tuple[CalendarModel, CalendarVersionModel]:
    now = datetime.datetime.now(datetime.UTC)
    calendar = CalendarModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
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
        week_number=1,
        label="1RA SEMANA",
        start_date=datetime.date(_YEAR, _MONTH, 2),
        end_date=datetime.date(_YEAR, _MONTH, 8),
        status=status,
    )
    db_session.add(week)
    db_session.flush()
    return week


def _create_doctor(
    db_session,
    *,
    name: str,
    allowed_area_ids: list[str] | None = None,
    monthly_max: int = 999,
    monthly_limit_mode: str = "warn_only",
) -> DoctorModel:
    now = datetime.datetime.now(datetime.UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name=name,
        normalized_name=" ".join(name.strip().lower().split()),
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        active=True,
        service_active=True,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=monthly_max,
        monthly_service_limit_mode=monthly_limit_mode,
        availability_mode="monthly",
        created_by="actor-001",
        created_at=now,
        updated_at=now,
        deactivated_at=None,
        deactivated_by=None,
    )
    db_session.add(doctor)
    db_session.flush()

    for area_id in (allowed_area_ids or []):
        db_session.add(
            DoctorAllowedAreaModel(doctor_id=doctor.id, service_area_id=area_id)
        )
    db_session.flush()

    return doctor


def _make_generation_service(db_session) -> GenerationService:
    return GenerationService(
        CalendarRepository(db_session),
        DoctorRepository(db_session),
        AvailabilityRepository(db_session),
        MissionRepository(db_session),
        CatalogRepository(db_session),
    )


def _make_assignment_service(db_session) -> AssignmentService:
    return AssignmentService(
        CalendarRepository(db_session),
        DoctorRepository(db_session),
        AvailabilityRepository(db_session),
    )


# ---------------------------------------------------------------------------
# test_full_lifecycle_generate_and_manual_adjust
# ---------------------------------------------------------------------------


def test_full_lifecycle_generate_and_manual_adjust(db_session) -> None:
    """Generate a calendar, then manually remove and re-assign a slot.

    Uses warn_only + high monthly_max so manual assignment after generation
    is not blocked by the hard limit.
    """
    _seed_service_areas(db_session)
    calendar, version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, version, status="draft")

    doctor_a = _create_doctor(
        db_session, name="Dr. A",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )
    doctor_b = _create_doctor(
        db_session, name="Dr. B",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )

    gen_service = _make_generation_service(db_session)
    summary = gen_service.generate(actor_id="actor-001", calendar_id=calendar.id)

    assert summary.assigned_count > 0, "Generation should produce assignments"

    cal_repo = CalendarRepository(db_session)
    assignments = cal_repo.list_assignments(version.id)

    assignment_to_replace = next(
        (a for a in assignments if a.doctor_id == doctor_a.id), None
    )
    assert assignment_to_replace is not None, "Doctor A should have at least one assignment"

    assign_service = _make_assignment_service(db_session)

    # Remove the assignment
    assign_service.remove_assignment(
        actor_id="actor-001", assignment_id=assignment_to_replace.id,
    )
    assert cal_repo.get_assignment_by_id(assignment_to_replace.id) is None

    # Re-assign doctor_b to the freed slot.
    # Use override_justification because doctor_b may have spacing warnings
    # from their existing generated assignments.
    new_assignment = assign_service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor_b.id,
        date=assignment_to_replace.service_date,
        service_area_id=assignment_to_replace.service_area_id,
        override_justification="Reemplazo manual autorizado.",
    )
    assert new_assignment.doctor_id == doctor_b.id
    assert new_assignment.service_date == assignment_to_replace.service_date


# ---------------------------------------------------------------------------
# test_generation_is_deterministic
# ---------------------------------------------------------------------------


def test_generation_is_deterministic(db_session) -> None:
    """Two fresh calendars with identical inputs produce identical assignment counts.

    Note: Re-generating on the SAME calendar loads the first run's results as
    existing_assignments (the engine treats them as manually placed), so a
    re-generation on the same calendar will differ. Determinism is measured
    across separate calendars with identical configs.
    """
    _seed_service_areas(db_session)

    # Create two identical calendars
    cal1, _v1 = _create_calendar_and_version(db_session)
    _create_week(db_session, cal1, _v1, status="draft")
    cal2, _v2 = _create_calendar_and_version(db_session)
    _create_week(db_session, cal2, _v2, status="draft")

    # Same doctors for both
    doctor_a = _create_doctor(
        db_session, name="Dr. A",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )
    doctor_b = _create_doctor(
        db_session, name="Dr. B",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )

    gen_service = _make_generation_service(db_session)

    summary1 = gen_service.generate(actor_id="actor-001", calendar_id=cal1.id)
    count_a1 = sum(1 for r in summary1.slot_results if r.assigned_doctor_id == doctor_a.id)
    count_b1 = sum(1 for r in summary1.slot_results if r.assigned_doctor_id == doctor_b.id)

    summary2 = gen_service.generate(actor_id="actor-001", calendar_id=cal2.id)
    count_a2 = sum(1 for r in summary2.slot_results if r.assigned_doctor_id == doctor_a.id)
    count_b2 = sum(1 for r in summary2.slot_results if r.assigned_doctor_id == doctor_b.id)

    assert count_a1 == count_a2, (
        f"Non-deterministic: doctor A got {count_a1} on cal1 vs {count_a2} on cal2"
    )
    assert count_b1 == count_b2, (
        f"Non-deterministic: doctor B got {count_b1} on cal1 vs {count_b2} on cal2"
    )


# ---------------------------------------------------------------------------
# test_manual_assignment_fills_generated_gap
# ---------------------------------------------------------------------------


def test_manual_assignment_fills_generated_gap(db_session) -> None:
    """Generate with 1 doctor, then manually assign to fill a gap.

    The gap row must be automatically deleted when a manual assignment
    covers its (date, area) slot.
    """
    _seed_service_areas(db_session)
    calendar, version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, version, status="draft")

    doctor1 = _create_doctor(
        db_session, name="Dr. Solo",
        allowed_area_ids=[_AREA_EMERGENCIA],
    )

    gen_service = _make_generation_service(db_session)
    summary = gen_service.generate(actor_id="actor-001", calendar_id=calendar.id)

    assert summary.gap_count > 0, "Expected gaps with single doctor covering only one area"

    cal_repo = CalendarRepository(db_session)
    gaps = cal_repo.list_gaps(version.id)
    assert len(gaps) > 0, "Gaps should exist in DB"
    gap = gaps[0]

    doctor2 = _create_doctor(
        db_session, name="Dr. Refuerzo",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )

    assign_service = _make_assignment_service(db_session)
    assignment = assign_service.assign_doctor(
        actor_id="actor-001",
        version_id=version.id,
        doctor_id=doctor2.id,
        date=gap.service_date,
        service_area_id=gap.service_area_id,
    )

    assert assignment.doctor_id == doctor2.id
    assert assignment.service_date == gap.service_date

    # The assignment was created successfully. Verify it exists in DB.
    stored = cal_repo.get_assignment_by_id(assignment.id)
    assert stored is not None
    assert stored.doctor_id == doctor2.id

    # The gap MUST be deleted — manual assignment resolves the gap.
    gaps_after = cal_repo.list_gaps(version.id)
    gap_ids = {g.id for g in gaps_after}
    assert gap.id not in gap_ids, "Gap must be deleted when a manual assignment covers its slot"
