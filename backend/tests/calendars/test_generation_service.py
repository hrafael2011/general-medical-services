"""
DB-backed integration tests for GenerationService.

Uses the in-memory SQLite db_session fixture from conftest.py.
Follows the ORM-direct pattern from test_assignment_service.py.
"""

import datetime
from uuid import uuid4

import pytest

from backend.app.application.calendars.errors import CalendarServiceError
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
# Fixed area IDs that match the generation engine's required_areas list
# ---------------------------------------------------------------------------

_AREA_EMERGENCIA = "emergencia"
_AREA_PISTA = "pista"
_AREA_DISPONIBLE = "disponible"

# Test month: February 2026 (28 days, 3 areas → 84 total slots)
_YEAR = 2026
_MONTH = 2


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


def _make_generation_service(db_session) -> GenerationService:
    return GenerationService(
        CalendarRepository(db_session),
        DoctorRepository(db_session),
        AvailabilityRepository(db_session),
        MissionRepository(db_session),
        CatalogRepository(db_session),
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _seed_service_areas(db_session) -> None:
    """Insert the three service area rows required by FK constraints."""
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
    """Create a CalendarModel + draft CalendarVersionModel for the test month."""
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
    service_active: bool = True,
    active: bool = True,
    allowed_area_ids: list[str] | None = None,
) -> DoctorModel:
    """Insert a DoctorModel and its allowed area rows directly via ORM."""
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
        active=active,
        service_active=service_active,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=6,
        monthly_service_limit_mode="warn_only",
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


# ---------------------------------------------------------------------------
# test_generate_assigns_doctors
# ---------------------------------------------------------------------------


def test_generate_assigns_doctors(db_session) -> None:
    """With three service-active doctors each covering one area, generation
    should produce assignments for every slot (28 days × 3 areas = 84).
    """
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)

    _create_doctor(db_session, name="Dr. Emergencia", allowed_area_ids=[_AREA_EMERGENCIA])
    _create_doctor(db_session, name="Dr. Pista", allowed_area_ids=[_AREA_PISTA])
    _create_doctor(db_session, name="Dr. Disponible", allowed_area_ids=[_AREA_DISPONIBLE])

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    # Each doctor owns exactly one area → one assignment per day per area
    assert summary.assigned_count > 0
    assert summary.assigned_count + summary.gap_count == summary.total_slots

    cal_repo = CalendarRepository(db_session)
    version = cal_repo.get_latest_version(calendar.id)
    assignments = cal_repo.list_assignments(version.id)
    assert len(assignments) == summary.assigned_count

    updated_calendar = cal_repo.get_calendar_by_id(calendar.id)
    assert updated_calendar.generation_mode == "assisted_auto"
    assert updated_calendar.status == "draft"
    assert version.status == "draft"


def test_generate_reports_missing_required_service_areas(db_session) -> None:
    calendar, _version = _create_calendar_and_version(db_session)

    service = _make_generation_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.generate(actor_id="actor-001", calendar_id=calendar.id)

    assert exc_info.value.code == "generation_configuration_incomplete"
    assert "emergencia" in exc_info.value.message


def test_generate_does_not_create_mission_ranking_before_approval(db_session) -> None:
    """Calendar generation must not create mission rankings for draft calendars."""
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)

    _create_doctor(db_session, name="Dr. Emergencia", allowed_area_ids=[_AREA_EMERGENCIA])

    service = _make_generation_service(db_session)
    service.generate(actor_id="actor-001", calendar_id=calendar.id)

    ranking = MissionRepository(db_session).get_ranking_by_period(_YEAR, _MONTH)
    assert ranking is None


def test_generate_fails_when_any_week_is_approved(db_session) -> None:
    """Generation must not overwrite assignments once a week is approved."""
    _seed_service_areas(db_session)
    calendar, version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, version, status="approved")

    service = _make_generation_service(db_session)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.generate(actor_id="actor-001", calendar_id=calendar.id)

    assert exc_info.value.code == "week_locked"


# ---------------------------------------------------------------------------
# test_generate_creates_gaps_when_no_doctors
# ---------------------------------------------------------------------------


def test_generate_creates_gaps_when_no_doctors(db_session) -> None:
    """When there are no service-active doctors, every slot must become a gap."""
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)

    # Deliberately create no doctors

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    assert summary.assigned_count == 0
    assert summary.gap_count == summary.total_slots

    cal_repo = CalendarRepository(db_session)
    version = cal_repo.get_latest_version(calendar.id)
    gaps = cal_repo.list_gaps(version.id)
    assert len(gaps) == summary.gap_count


# ---------------------------------------------------------------------------
# test_generate_clears_previous_assignments
# ---------------------------------------------------------------------------


def test_generate_clears_previous_assignments(db_session) -> None:
    """Calling generate twice must not duplicate assignments.

    After two successive generations the total assignment count for the
    version must equal exactly the second generation's assigned_count —
    not double it.
    """
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)

    _create_doctor(db_session, name="Dr. Emergencia", allowed_area_ids=[_AREA_EMERGENCIA])
    _create_doctor(db_session, name="Dr. Pista", allowed_area_ids=[_AREA_PISTA])
    _create_doctor(db_session, name="Dr. Disponible", allowed_area_ids=[_AREA_DISPONIBLE])

    service = _make_generation_service(db_session)

    service.generate(actor_id="actor-001", calendar_id=calendar.id)
    summary_second = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    cal_repo = CalendarRepository(db_session)
    version = cal_repo.get_latest_version(calendar.id)
    assignments_in_db = cal_repo.list_assignments(version.id)
    gaps_in_db = cal_repo.list_gaps(version.id)

    # The DB must reflect the second generation only — no duplicates.
    assert len(assignments_in_db) == summary_second.assigned_count
    assert len(gaps_in_db) == summary_second.gap_count
    # Sanity: totals add up correctly.
    assert len(assignments_in_db) + len(gaps_in_db) == summary_second.total_slots


# ---------------------------------------------------------------------------
# test_generate_respects_monthly_max_hard_limit
# ---------------------------------------------------------------------------


def test_generate_respects_monthly_max_hard_limit(db_session) -> None:
    """A doctor with monthly_service_max=2 (hard_limit) gets at most 2 assignments."""
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, _version, status="draft")

    doctor = _create_doctor(
        db_session, name="Dr. Limited",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )
    doctor.monthly_service_max = 2
    doctor.monthly_service_limit_mode = "hard_limit"
    db_session.flush()

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    doctor_assignments = [
        r for r in summary.slot_results
        if r.assigned_doctor_id == doctor.id
    ]
    assert len(doctor_assignments) == 2, (
        f"Expected 2 assignments (max=2 hard_limit), got {len(doctor_assignments)}"
    )


# ---------------------------------------------------------------------------
# test_generate_distributes_across_doctors_in_same_area
# ---------------------------------------------------------------------------


def test_generate_distributes_across_doctors_in_same_area(db_session) -> None:
    """With 2 doctors for the same area, both should get assignments."""
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, _version, status="draft")

    doctor_a = _create_doctor(
        db_session, name="Dr. A", allowed_area_ids=[_AREA_EMERGENCIA],
    )
    doctor_b = _create_doctor(
        db_session, name="Dr. B", allowed_area_ids=[_AREA_EMERGENCIA],
    )

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    count_a = sum(1 for r in summary.slot_results if r.assigned_doctor_id == doctor_a.id)
    count_b = sum(1 for r in summary.slot_results if r.assigned_doctor_id == doctor_b.id)

    assert count_a > 0, f"Doctor A got 0 assignments — unfair distribution"
    assert count_b > 0, f"Doctor B got 0 assignments — unfair distribution"


# ---------------------------------------------------------------------------
# test_generate_respects_hard_block
# ---------------------------------------------------------------------------


def test_generate_respects_hard_block(db_session) -> None:
    """A doctor with a hard_block restriction gets 0 assignments."""
    from backend.app.infrastructure.db.models.availability import DoctorRestrictionModel

    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, _version, status="draft")

    doctor = _create_doctor(
        db_session, name="Dr. Blocked",
        allowed_area_ids=[_AREA_EMERGENCIA, _AREA_PISTA, _AREA_DISPONIBLE],
    )

    now = datetime.datetime.now(datetime.UTC)
    db_session.add(DoctorRestrictionModel(
        id=str(uuid4()),
        doctor_id=doctor.id,
        restriction_type="licencia",
        severity="hard_block",
        starts_at=datetime.date(2026, 1, 26),
        ends_at=None,
        lifted_at=None,
        description="Test block",
        source="manual",
        created_by="actor-001",
        created_at=now,
        updated_at=now,
    ))
    db_session.flush()

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    doctor_assignments = [
        r for r in summary.slot_results
        if r.assigned_doctor_id == doctor.id
    ]
    assert len(doctor_assignments) == 0, (
        f"Doctor with hard_block should have 0 assignments, got {len(doctor_assignments)}"
    )


# ---------------------------------------------------------------------------
# test_generate_with_partial_area_coverage
# ---------------------------------------------------------------------------


def test_generate_with_partial_area_coverage(db_session) -> None:
    """When doctors only cover 2 of 3 areas, the uncovered area is all gaps."""
    _seed_service_areas(db_session)
    calendar, _version = _create_calendar_and_version(db_session)
    _create_week(db_session, calendar, _version, status="draft")

    _create_doctor(
        db_session, name="Dr. Emergencia",
        allowed_area_ids=[_AREA_EMERGENCIA],
    )
    _create_doctor(
        db_session, name="Dr. Pista",
        allowed_area_ids=[_AREA_PISTA],
    )

    service = _make_generation_service(db_session)
    summary = service.generate(actor_id="actor-001", calendar_id=calendar.id)

    disponible_gaps = sum(
        1 for r in summary.slot_results
        if r.slot.service_area_id == _AREA_DISPONIBLE and r.assigned_doctor_id is None
    )
    emergencia_assigned = sum(
        1 for r in summary.slot_results
        if r.slot.service_area_id == _AREA_EMERGENCIA and r.assigned_doctor_id is not None
    )
    assert disponible_gaps > 0, "Disponible should have gaps (no doctor covers it)"
    assert emergencia_assigned > 0, "Emergencia should have assignments"
