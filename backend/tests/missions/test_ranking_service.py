"""
DB-backed integration tests for MissionRankingService.

Uses the in-memory SQLite db_session fixture from conftest.py.
Creates ORM models directly without going through service layers.
"""

import datetime
from uuid import uuid4

from sqlalchemy import select

from backend.app.application.missions.ranking_service import MissionRankingService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import MissionCandidateRankingModel
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_YEAR = 2026
_MONTH = 5
_ACTOR = "actor-test"


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


def _make_ranking_service(db_session) -> MissionRankingService:
    return MissionRankingService(
        MissionRepository(db_session),
        DoctorRepository(db_session),
        CalendarRepository(db_session),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _create_doctor(
    db_session,
    *,
    name: str,
    participa_misiones: bool = True,
    service_active: bool = True,
    active: bool = True,
) -> DoctorModel:
    now = _now()
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
        participa_misiones=participa_misiones,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=6,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_by=_ACTOR,
        created_at=now,
        updated_at=now,
        deactivated_at=None,
        deactivated_by=None,
    )
    db_session.add(doctor)
    db_session.flush()
    return doctor


def _create_calendar_version(db_session) -> CalendarVersionModel:
    """Create a minimal CalendarModel + CalendarVersionModel for use as FK."""
    now = _now()
    calendar = CalendarModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
        status="draft",
        created_by=_ACTOR,
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
        created_by=_ACTOR,
        reason=None,
        created_at=now,
    )
    db_session.add(version)
    db_session.flush()
    return version


def _add_assignment(
    db_session,
    *,
    calendar_version_id: str,
    doctor_id: str,
    service_date: datetime.date,
    service_area_id: str = "emergencia",
) -> CalendarAssignmentModel:
    """Insert a CalendarAssignmentModel directly.

    SQLite does not enforce FK constraints, so service_area_id can be any
    string without a matching ServiceAreaModel row.
    """
    now = _now()
    assignment = CalendarAssignmentModel(
        id=str(uuid4()),
        calendar_version_id=calendar_version_id,
        service_date=service_date,
        service_start_at=None,
        service_area_id=service_area_id,
        doctor_id=doctor_id,
        assignment_source="manual",
        rationale=None,
        override_justification=None,
        created_by=_ACTOR,
        created_at=now,
    )
    db_session.add(assignment)
    db_session.flush()
    return assignment


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_generate_ranking_excludes_no_mission_doctors(db_session) -> None:
    """Doctors with participa_misiones=False must not appear in the ranking."""
    _create_doctor(db_session, name="Dr. Eligible", participa_misiones=True)
    _create_doctor(db_session, name="Dr. No Mission", participa_misiones=False)

    service = _make_ranking_service(db_session)
    ranking = service.generate_ranking(actor_id=_ACTOR, year=_YEAR, month=_MONTH)

    repo = MissionRepository(db_session)
    entries = repo.list_ranking_entries(ranking.id)

    assert len(entries) == 1
    assert entries[0].doctor_id is not None


def test_generate_ranking_orders_by_load(db_session) -> None:
    """The doctor with more calendar assignments should have a higher ranking position
    (i.e. higher position number — worse rank, since positions are 1-based ascending by load).
    """
    version = _create_calendar_version(db_session)

    doctor_low = _create_doctor(db_session, name="Dr. Low Load")
    doctor_high = _create_doctor(db_session, name="Dr. High Load")

    # Give doctor_high two assignments in the ranking month
    first_day = datetime.date(_YEAR, _MONTH, 1)
    _add_assignment(
        db_session,
        calendar_version_id=version.id,
        doctor_id=doctor_high.id,
        service_date=first_day,
    )
    _add_assignment(
        db_session,
        calendar_version_id=version.id,
        doctor_id=doctor_high.id,
        service_date=first_day.replace(day=2),
    )
    # doctor_low gets no assignments

    service = _make_ranking_service(db_session)
    ranking = service.generate_ranking(actor_id=_ACTOR, year=_YEAR, month=_MONTH)

    repo = MissionRepository(db_session)
    entries = repo.list_ranking_entries(ranking.id)

    assert len(entries) == 2

    by_doctor = {e.doctor_id: e for e in entries}
    assert by_doctor[doctor_low.id].ranking_position < by_doctor[doctor_high.id].ranking_position


def test_generate_ranking_regenerates(db_session) -> None:
    """Calling generate_ranking twice must not create duplicate ranking rows."""
    _create_doctor(db_session, name="Dr. One")

    service = _make_ranking_service(db_session)
    service.generate_ranking(actor_id=_ACTOR, year=_YEAR, month=_MONTH)
    service.generate_ranking(actor_id=_ACTOR, year=_YEAR, month=_MONTH)

    stmt = select(MissionCandidateRankingModel).where(
        MissionCandidateRankingModel.year == _YEAR,
        MissionCandidateRankingModel.month == _MONTH,
    )
    rows = list(db_session.scalars(stmt))
    assert len(rows) == 1


def test_get_ranking_returns_none_when_missing(db_session) -> None:
    """get_ranking must return None for a period with no generated ranking."""
    service = _make_ranking_service(db_session)
    result = service.get_ranking(year=2030, month=1)
    assert result is None
