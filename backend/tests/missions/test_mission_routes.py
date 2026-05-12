import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import require_ready_user
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import audit as _audit  # noqa: F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: F401
from backend.app.infrastructure.db.models import doctors as _doctors  # noqa: F401
from backend.app.infrastructure.db.models import missions as _missions  # noqa: F401
from backend.app.infrastructure.db.models import notifications as _notifications  # noqa: F401
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: F401
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.models.calendars import CalendarModel, CalendarVersionModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
)
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app

_YEAR = 2026
_MONTH = 5
_ACTOR = "actor-test"


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def user():
    return _user.UserModel(
        id=_ACTOR,
        email="actor@example.com",
        password_hash="hash",
        name="Actor Test",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=datetime.datetime.now(datetime.UTC),
    )


@pytest.fixture()
def client(session, user):
    app = create_app()

    def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[require_ready_user] = lambda: user
    return TestClient(app)


def _create_calendar_version(session, *, approved: bool) -> CalendarVersionModel:
    now = datetime.datetime.now(datetime.UTC)
    calendar = CalendarModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
        status="approved" if approved else "draft",
        created_by=_ACTOR,
        approved_by=_ACTOR if approved else None,
        created_at=now,
        updated_at=now,
        approved_at=now if approved else None,
    )
    session.add(calendar)
    session.flush()

    version = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status="approved" if approved else "draft",
        created_by=_ACTOR,
        reason=None,
        created_at=now,
        approved_at=now if approved else None,
        approved_by=_ACTOR if approved else None,
    )
    session.add(version)
    session.flush()
    return version


def _create_doctor(session) -> DoctorModel:
    now = datetime.datetime.now(datetime.UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Dr. Ruta",
        normalized_name="dr. ruta",
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
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_by=_ACTOR,
        created_at=now,
        updated_at=now,
        deactivated_at=None,
        deactivated_by=None,
    )
    session.add(doctor)
    session.flush()
    return doctor


def _create_ranking(session, *, version_id: str) -> None:
    doctor = _create_doctor(session)
    now = datetime.datetime.now(datetime.UTC)
    ranking = MissionCandidateRankingModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=version_id,
        generated_at=now,
        created_by=_ACTOR,
    )
    session.add(ranking)
    session.flush()
    session.add(
        MissionCandidateRankingEntryModel(
            id=str(uuid4()),
            mission_candidate_ranking_id=ranking.id,
            doctor_id=doctor.id,
            ranking_position=1,
            total_load_score=0,
            monthly_service_load=0,
            recent_service_load=0,
            monthly_mission_load=0,
            eligible=True,
            reasons=None,
            warnings=None,
        )
    )
    session.flush()


def test_get_ranking_requires_approved_calendar(client, session) -> None:
    draft_version = _create_calendar_version(session, approved=False)
    _create_ranking(session, version_id=draft_version.id)
    session.commit()

    response = client.get(f"/api/missions/rankings/{_YEAR}/{_MONTH}")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approved_calendar_required"


def test_get_ranking_uses_approved_calendar_version(client, session) -> None:
    approved_version = _create_calendar_version(session, approved=True)
    _create_ranking(session, version_id=approved_version.id)
    session.commit()

    response = client.get(f"/api/missions/rankings/{_YEAR}/{_MONTH}")

    assert response.status_code == 200
    data = response.json()
    assert data["calendar_version_id"] == approved_version.id
    assert data["entries"][0]["doctor_name"] == "Dr. Ruta"


def _create_mission(session, *, status: str = "draft") -> MissionAssignmentModel:
    now = datetime.datetime.now(datetime.UTC)
    mission = MissionAssignmentModel(
        id=str(uuid4()),
        mission_date=datetime.date(2026, 5, 20),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=2,
        location="Base Norte",
        description=None,
        source="manual",
        status=status,
        created_by=_ACTOR,
        confirmed_by=None,
        confirmed_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    session.add(mission)
    session.flush()
    return mission


def test_update_mission_edits_basic_fields(client, session) -> None:
    mission = _create_mission(session)
    session.commit()

    response = client.patch(
        f"/api/missions/{mission.id}",
        json={
            "mission_date": "2026-05-22",
            "participant_count": 4,
            "location": "Base Sur",
            "description": "Operativo especial",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mission_date"] == "2026-05-22"
    assert data["participant_count"] == 4
    assert data["location"] == "Base Sur"
    assert data["description"] == "Operativo especial"


def test_delete_mission_is_soft_delete_and_hides_from_list(client, session) -> None:
    mission = _create_mission(session)
    session.commit()

    response = client.delete(f"/api/missions/{mission.id}")

    assert response.status_code == 204
    assert mission.deleted_at is not None
    list_response = client.get("/api/missions")
    assert list_response.status_code == 200
    assert list_response.json() == []
    get_response = client.get(f"/api/missions/{mission.id}")
    assert get_response.status_code == 404


def test_confirm_mission_accepts_path_id_and_doctor_ids_body(client, session) -> None:
    approved_version = _create_calendar_version(session, approved=True)
    doctor = _create_doctor(session)
    now = datetime.datetime.now(datetime.UTC)
    ranking = MissionCandidateRankingModel(
        id=str(uuid4()),
        year=_YEAR,
        month=_MONTH,
        calendar_version_id=approved_version.id,
        generated_at=now,
        created_by=_ACTOR,
    )
    session.add(ranking)
    session.flush()
    session.add(
        MissionCandidateRankingEntryModel(
            id=str(uuid4()),
            mission_candidate_ranking_id=ranking.id,
            doctor_id=doctor.id,
            ranking_position=1,
            total_load_score=0,
            monthly_service_load=0,
            recent_service_load=0,
            monthly_mission_load=0,
            eligible=True,
            reasons=None,
            warnings=None,
        )
    )
    mission = _create_mission(session)
    session.commit()

    response = client.post(
        f"/api/missions/{mission.id}/confirm",
        json={"doctor_ids": [doctor.id]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["participants"][0]["doctor_name"] == "Dr. Ruta"
