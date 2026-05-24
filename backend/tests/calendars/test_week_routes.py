"""Tests for calendar week API endpoints."""
from datetime import date, datetime, UTC
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
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
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


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
        id="test-actor",
        email="actor@example.com",
        password_hash="hash",
        name="Actor Test",
        role="admin",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture()
def client(session, user):
    app = create_app()

    def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _create_calendar_version(
    session,
    *,
    calendar_id: str | None = None,
    status: str = "draft",
) -> tuple[CalendarModel, CalendarVersionModel]:
    now = datetime.now(UTC)
    cal_id = calendar_id or f"cal-{uuid4().hex[:8]}"
    calendar = CalendarModel(
        id=cal_id,
        year=2026,
        month=5,
        status=status,
        generation_mode="manual",
        created_by="test-actor",
        approved_by=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
    )
    session.add(calendar)
    session.flush()

    version = CalendarVersionModel(
        id=f"ver-{uuid4().hex[:8]}",
        calendar_id=calendar.id,
        version_number=1,
        status="draft",
        created_by="test-actor",
        reason=None,
        created_at=now,
    )
    session.add(version)
    session.flush()
    return calendar, version


def _create_week(session, *, calendar_id: str, version_id: str, **kw) -> CalendarWeekModel:
    overrides = {
        "id": kw.get("id", f"w-{uuid4().hex[:8]}"),
        "calendar_id": calendar_id,
        "calendar_version_id": version_id,
        "week_number": kw.get("week_number", 1),
        "label": kw.get("label", "1RA SEMANA"),
        "start_date": kw.get("start_date", date(2026, 5, 4)),
        "end_date": kw.get("end_date", date(2026, 5, 10)),
        "status": kw.get("status", "draft"),
    }
    week = CalendarWeekModel(**overrides)
    session.add(week)
    session.flush()
    return week


def _create_doctor(session, *, doctor_id: str, name: str) -> DoctorModel:
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=doctor_id,
        name=name,
        normalized_name=name.lower(),
        sex="male",
        active=True,
        service_active=True,
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_at=now,
        updated_at=now,
    )
    session.add(doctor)
    session.flush()
    return doctor


def _create_assignment(
    session,
    *,
    version_id: str,
    doctor_id: str,
    service_date: date,
    area_id: str,
) -> CalendarAssignmentModel:
    assignment = CalendarAssignmentModel(
        id=f"a-{uuid4().hex[:8]}",
        calendar_version_id=version_id,
        service_date=service_date,
        service_area_id=area_id,
        doctor_id=doctor_id,
        assignment_source="manual",
        created_at=datetime.now(UTC),
    )
    session.add(assignment)
    session.flush()
    return assignment


def test_list_weeks_returns_weeks(client, session):
    """GET /calendars/{id}/weeks returns week list with statuses."""
    cal, ver = _create_calendar_version(session, calendar_id="cal-w1")
    _create_week(
        session,
        id="w1",
        calendar_id=cal.id,
        version_id=ver.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="draft",
    )
    session.flush()

    response = client.get("/api/calendars/cal-w1/weeks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["label"] == "1RA SEMANA"
    assert data[0]["status"] == "draft"


def test_list_weeks_returns_doctor_assignment_counts(client, session):
    cal, ver = _create_calendar_version(session, calendar_id="cal-week-counts")
    _create_week(
        session,
        id="w-counts",
        calendar_id=cal.id,
        version_id=ver.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="draft",
    )
    _create_doctor(session, doctor_id="doc-a", name="Dr. A")
    _create_doctor(session, doctor_id="doc-b", name="Dr. B")
    _create_assignment(
        session,
        version_id=ver.id,
        doctor_id="doc-a",
        service_date=date(2026, 5, 4),
        area_id="area-1",
    )
    _create_assignment(
        session,
        version_id=ver.id,
        doctor_id="doc-a",
        service_date=date(2026, 5, 5),
        area_id="area-1",
    )
    _create_assignment(
        session,
        version_id=ver.id,
        doctor_id="doc-b",
        service_date=date(2026, 5, 6),
        area_id="area-1",
    )

    response = client.get("/api/calendars/cal-week-counts/weeks")

    assert response.status_code == 200
    counts = response.json()[0]["doctor_assignment_counts"]
    assert counts == [
        {"doctor_id": "doc-a", "doctor_name": "Dr. A", "count": 2},
        {"doctor_id": "doc-b", "doctor_name": "Dr. B", "count": 1},
    ]


def test_approve_week_endpoint(client, session):
    """POST /calendars/{id}/weeks/{week_id}/approve triggers approval."""
    cal, ver = _create_calendar_version(session, calendar_id="cal-w2")
    _create_week(
        session,
        id="w2",
        calendar_id=cal.id,
        version_id=ver.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="draft",
    )
    session.flush()

    response = client.post(
        "/api/calendars/cal-w2/weeks/w2/approve",
        json={"notes": "aprobado"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"


def test_unlock_week_endpoint(client, session):
    """POST /calendars/{id}/weeks/{week_id}/unlock reverts week to draft."""
    cal, ver = _create_calendar_version(session, calendar_id="cal-w3")
    _create_week(
        session,
        id="w3",
        calendar_id=cal.id,
        version_id=ver.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="approved",
    )
    session.flush()

    response = client.post(
        "/api/calendars/cal-w3/weeks/w3/unlock",
        json={"notes": "correccion"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"
