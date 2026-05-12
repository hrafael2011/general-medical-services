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
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
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
        CatalogRepository(db_session),
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


def _create_service_area(db_session, *, code: str, display_name: str) -> ServiceAreaModel:
    now = _now()
    area = ServiceAreaModel(
        id=str(uuid4()),
        code=code,
        display_name=display_name,
        active=True,
        required_for_daily_coverage=True,
        load_weight=3 if code == "emergencia" else 2 if code == "pista" else 1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(area)
    db_session.flush()
    return area


def _create_approved_calendar_version(db_session) -> CalendarVersionModel:
    now = _now()
    calendar = CalendarModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
        status="approved",
        created_by=_ACTOR,
        approved_by=_ACTOR,
        created_at=now,
        updated_at=now,
        approved_at=now,
    )
    db_session.add(calendar)
    db_session.flush()

    version = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status="approved",
        created_by=_ACTOR,
        reason=None,
        created_at=now,
        approved_at=now,
        approved_by=_ACTOR,
    )
    db_session.add(version)
    db_session.flush()
    return version


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

    assert exc_info.value.code == "approved_calendar_required"


def test_rank_candidates_for_date_marks_same_day_service_unavailable(db_session) -> None:
    """Full date ranking must keep all candidates and push same-day conflicts down."""
    doctor_a = _create_doctor(db_session, name="Dr. A")
    doctor_b = _create_doctor(db_session, name="Dr. B")
    version = _create_approved_calendar_version(db_session)

    ranking_service = _make_ranking_service(db_session)
    ranking_service.generate_ranking(
        actor_id=_ACTOR,
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version.id,
    )

    db_session.add(
        CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version.id,
            service_date=_MISSION_DATE,
            service_start_at=None,
            service_area_id="emergencia",
            doctor_id=doctor_a.id,
            assignment_source="manual",
            rationale=None,
            override_justification=None,
            created_by=_ACTOR,
            created_at=_now(),
        )
    )
    db_session.flush()

    service = _make_candidate_service(db_session)
    ranked = service.rank_candidates_for_date(
        year=_YEAR,
        month=_MONTH,
        mission_date=_MISSION_DATE,
    )

    assert [item["entry"].doctor_id for item in ranked] == [doctor_b.id]
    assert ranked[0]["recommendation_status"] == "recommended"
    assert ranked[0]["adjusted_position"] == 1


def test_rank_candidates_for_date_detects_recent_strong_area_stored_as_uuid(db_session) -> None:
    """Recent strong services are persisted with area UUIDs and must still warn."""
    doctor = _create_doctor(db_session, name="Dr. Fuerte")
    version = _create_approved_calendar_version(db_session)
    emergencia = _create_service_area(
        db_session,
        code="emergencia",
        display_name="Emergencia",
    )

    ranking_service = _make_ranking_service(db_session)
    ranking_service.generate_ranking(
        actor_id=_ACTOR,
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version.id,
    )

    db_session.add(
        CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version.id,
            service_date=_MISSION_DATE - datetime.timedelta(days=3),
            service_start_at=None,
            service_area_id=emergencia.id,
            doctor_id=doctor.id,
            assignment_source="manual",
            rationale=None,
            override_justification=None,
            created_by=_ACTOR,
            created_at=_now(),
        )
    )
    db_session.flush()

    service = _make_candidate_service(db_session)
    ranked = service.rank_candidates_for_date(
        year=_YEAR,
        month=_MONTH,
        mission_date=_MISSION_DATE,
    )

    item = next(item for item in ranked if item["entry"].doctor_id == doctor.id)
    assert item["recommendation_status"] == "alternate"
    assert item["selectable"] is True
    assert any("servicio fuerte reciente" in warning.lower() for warning in item["warnings"])


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
    version = _create_approved_calendar_version(db_session)

    ranking_service = _make_ranking_service(db_session)
    ranking_service.generate_ranking(
        actor_id=_ACTOR,
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version.id,
    )

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


def test_confirm_mission_rejects_same_day_service_doctor(db_session) -> None:
    """Confirming a mission must reject doctors who already have service that day."""
    doctor = _create_doctor(db_session, name="Dr. Ocupado")
    version = _create_approved_calendar_version(db_session)

    ranking_service = _make_ranking_service(db_session)
    ranking_service.generate_ranking(
        actor_id=_ACTOR,
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version.id,
    )

    db_session.add(
        CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version.id,
            service_date=_MISSION_DATE,
            service_start_at=None,
            service_area_id="emergencia",
            doctor_id=doctor.id,
            assignment_source="manual",
            rationale=None,
            override_justification=None,
            created_by=_ACTOR,
            created_at=_now(),
        )
    )
    db_session.flush()

    service = _make_candidate_service(db_session)
    mission = service.create_mission(
        actor_id=_ACTOR,
        mission_date=_MISSION_DATE,
        participant_count=1,
        location=None,
        description=None,
    )

    with pytest.raises(MissionServiceError) as exc_info:
        service.confirm_mission(
            actor_id=_ACTOR,
            mission_id=mission.id,
            doctor_ids=[doctor.id],
        )

    assert exc_info.value.code == "candidate_not_available"


def test_confirm_already_confirmed_raises(db_session) -> None:
    """Confirming a mission that is already confirmed must raise
    MissionServiceError with code='already_confirmed'."""
    doctor = _create_doctor(db_session, name="Dr. Solo")
    version = _create_approved_calendar_version(db_session)

    ranking_service = _make_ranking_service(db_session)
    ranking_service.generate_ranking(
        actor_id=_ACTOR,
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version.id,
    )

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
