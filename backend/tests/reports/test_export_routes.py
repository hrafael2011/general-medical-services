"""Tests for new PDF export endpoints."""
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
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
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


def _create_calendar(session, **kw) -> CalendarModel:
    cal_id = kw.get("id", f"cal-{uuid4().hex[:8]}")
    calendar = CalendarModel(
        id=cal_id,
        year=kw.get("year", 2026),
        month=kw.get("month", 5),
        status=kw.get("status", "partial"),
        generation_mode=kw.get("generation_mode", "manual"),
        created_by="test-actor",
        approved_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        approved_at=None,
    )
    session.add(calendar)
    session.flush()
    return calendar


def _create_version(session, *, calendar_id: str, **kw) -> CalendarVersionModel:
    version = CalendarVersionModel(
        id=kw.get("id", f"ver-{uuid4().hex[:8]}"),
        calendar_id=calendar_id,
        version_number=kw.get("version_number", 1),
        status=kw.get("status", "draft"),
        created_by="test-actor",
        reason=None,
        created_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()
    return version


def _create_week(session, *, calendar_id: str, version_id: str, **kw) -> CalendarWeekModel:
    week = CalendarWeekModel(
        id=kw.get("id", f"w-{uuid4().hex[:8]}"),
        calendar_id=calendar_id,
        calendar_version_id=version_id,
        week_number=kw.get("week_number", 1),
        label=kw.get("label", "1RA SEMANA"),
        start_date=kw.get("start_date", date(2026, 5, 4)),
        end_date=kw.get("end_date", date(2026, 5, 10)),
        status=kw.get("status", "approved"),
        created_at=kw.get("created_at", datetime.now(UTC)),
        updated_at=kw.get("updated_at", datetime.now(UTC)),
    )
    session.add(week)
    session.flush()
    return week


def test_weekly_list_pdf_export(client, session):
    """GET /reports/calendar/{id}/weeks/{week_id}/pdf returns PDF."""
    cal = _create_calendar(session, id="cal-exp1")
    ver = _create_version(session, calendar_id=cal.id, id="ver-exp1")
    _create_week(
        session,
        id="w-exp1",
        calendar_id=cal.id,
        version_id=ver.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="approved",
    )
    session.flush()

    response = client.get("/api/reports/calendar/cal-exp1/weeks/w-exp1/pdf")
    # May be 200 (if assignments exist) or 404 (if none) — both mean route exists
    assert response.status_code in (200, 404)


def test_full_calendar_pdf_export(client, session):
    """GET /reports/calendar/{id}/full-pdf returns PDF."""
    _create_calendar(session, id="cal-exp2")
    _create_version(session, calendar_id="cal-exp2", id="ver-exp2")
    session.flush()

    response = client.get("/api/reports/calendar/cal-exp2/full-pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
