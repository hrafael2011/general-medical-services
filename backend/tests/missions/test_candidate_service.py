"""
DB-backed integration tests for MissionCandidateService.

Uses the in-memory SQLite db_session fixture from conftest.py.
Creates ORM models directly without going through higher-level layers.
"""

import datetime
from uuid import uuid4

import pytest

from backend.app.application.missions.candidate_service import MissionCandidateService
from backend.app.application.missions.errors import MissionServiceError
from backend.app.application.missions.ranking_service import MissionRankingService
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_YEAR = 2026
_MONTH = 5
_ACTOR = "actor-test"
_MISSION_DATE = datetime.date(_YEAR, _MONTH, 15)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def _make_candidate_service(db_session) -> MissionCandidateService:
    return MissionCandidateService(
        MissionRepository(db_session),
        CalendarRepository(db_session),
        AvailabilityRepository(db_session),
    )


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


def _create_doctor(db_session, *, name: str, participa_misiones: bool = True) -> DoctorModel:
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
        active=True,
        service_active=True,
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_recommend_without_ranking_raises(db_session) -> None:
    """recommend_candidates must raise MissionServiceError with code='ranking_not_found'
    when no ranking exists for the requested period."""
    service = _make_candidate_service(db_session)

    with pytest.raises(MissionServiceError) as exc_info:
        service.recommend_candidates(
            year=_YEAR,
            month=_MONTH,
            mission_date=_MISSION_DATE,
            participant_count=2,
        )

    assert exc_info.value.code == "ranking_not_found"


def test_create_mission(db_session) -> None:
    """create_mission must persist a MissionAssignmentModel with status='draft'."""
    service = _make_candidate_service(db_session)

    mission = service.create_mission(
        actor_id=_ACTOR,
        mission_date=_MISSION_DATE,
        participant_count=3,
        location="Base Norte",
        description="Operativo mensual",
    )

    assert mission.id is not None
    assert mission.status == "draft"
    assert mission.mission_date == _MISSION_DATE
    assert mission.participant_count == 3
    assert mission.location == "Base Norte"

    # Verify it was persisted
    repo = MissionRepository(db_session)
    fetched = repo.get_mission_by_id(mission.id)
    assert fetched is not None
    assert fetched.status == "draft"


def test_confirm_mission(db_session) -> None:
    """confirm_mission must set status='confirmed' and create participant rows."""
    doctor_a = _create_doctor(db_session, name="Dr. A")
    doctor_b = _create_doctor(db_session, name="Dr. B")

    service = _make_candidate_service(db_session)

    mission = service.create_mission(
        actor_id=_ACTOR,
        mission_date=_MISSION_DATE,
        participant_count=2,
        location=None,
        description=None,
    )

    confirmed = service.confirm_mission(
        actor_id=_ACTOR,
        mission_id=mission.id,
        doctor_ids=[doctor_a.id, doctor_b.id],
    )

    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_by == _ACTOR
    assert confirmed.confirmed_at is not None

    repo = MissionRepository(db_session)
    participants = repo.list_participants(mission.id)
    participant_doctor_ids = {p.doctor_id for p in participants}
    assert participant_doctor_ids == {doctor_a.id, doctor_b.id}


def test_confirm_already_confirmed_raises(db_session) -> None:
    """Confirming a mission that is already confirmed must raise
    MissionServiceError with code='already_confirmed'."""
    doctor = _create_doctor(db_session, name="Dr. Solo")

    service = _make_candidate_service(db_session)

    mission = service.create_mission(
        actor_id=_ACTOR,
        mission_date=_MISSION_DATE,
        participant_count=1,
        location=None,
        description=None,
    )

    # First confirm — should succeed
    service.confirm_mission(
        actor_id=_ACTOR,
        mission_id=mission.id,
        doctor_ids=[doctor.id],
    )

    # Second confirm — must raise
    with pytest.raises(MissionServiceError) as exc_info:
        service.confirm_mission(
            actor_id=_ACTOR,
            mission_id=mission.id,
            doctor_ids=[doctor.id],
        )

    assert exc_info.value.code == "already_confirmed"
