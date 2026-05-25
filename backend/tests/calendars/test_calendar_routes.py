"""Tests for calendars API routes — all services mocked."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.calendars import (
    get_assignment_service,
    get_calendar_service,
    get_generation_service,
)
from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_local(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture
def user():
    return UserModel(
        id="test-user", email="user@test.com", password_hash="hash", name="Test User",
        role="admin", active=True, must_change_password=False, token_version=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_calendar_service():
    return MagicMock(spec=CalendarService)


@pytest.fixture
def mock_generation_service():
    return MagicMock(spec=GenerationService)


@pytest.fixture
def mock_assignment_service():
    return MagicMock(spec=AssignmentService)


@pytest.fixture
def client(session_local, user, mock_calendar_service, mock_generation_service, mock_assignment_service):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_calendar_service] = lambda: mock_calendar_service
    app.dependency_overrides[get_generation_service] = lambda: mock_generation_service
    app.dependency_overrides[get_assignment_service] = lambda: mock_assignment_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calendar(**kw):
    fields = dict(
        id=str(uuid4()), month=5, year=2026, status="draft", generation_mode="assisted_auto",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    fields.update(kw)
    return CalendarModel(**fields)


def _make_version(**kw):
    fields = dict(
        id=str(uuid4()), calendar_id=str(uuid4()), version_number=1, status="draft",
        created_at=datetime.now(UTC),
    )
    fields.update(kw)
    return CalendarVersionModel(**fields)


def _make_assignment(**kw):
    fields = dict(
        id=str(uuid4()), calendar_version_id=str(uuid4()), doctor_id="doc-1",
        service_area_id="area-1", service_date="2026-05-01",
        assignment_source="manual", created_at=datetime.now(UTC),
    )
    fields.update(kw)
    return CalendarAssignmentModel(**fields)


# ---------------------------------------------------------------------------
# GET /api/calendars
# ---------------------------------------------------------------------------


def test_list_calendars(client, mock_calendar_service):
    mock_calendar_service.list_calendars.return_value = [_make_calendar()]
    resp = client.get("/api/calendars")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["month"] == 5


# ---------------------------------------------------------------------------
# POST /api/calendars
# ---------------------------------------------------------------------------


def test_create_calendar_success(client, mock_calendar_service):
    mock_calendar_service.create_calendar.return_value = _make_calendar(month=6)
    resp = client.post("/api/calendars", json={"month": 6, "year": 2026})
    assert resp.status_code == 201
    assert resp.json()["month"] == 6


def test_create_calendar_does_not_auto_generate_or_approve(
    client, mock_calendar_service, mock_generation_service
):
    mock_calendar_service.create_calendar.return_value = _make_calendar(
        month=6,
        generation_mode="assisted_auto",
    )

    resp = client.post(
        "/api/calendars",
        json={"month": 6, "year": 2026, "generation_mode": "assisted_auto"},
    )

    assert resp.status_code == 201
    mock_generation_service.generate.assert_not_called()
    mock_calendar_service.approve_version.assert_not_called()


def test_create_calendar_conflict(client, mock_calendar_service):
    mock_calendar_service.create_calendar.side_effect = CalendarServiceError(
        "calendar_already_exists", "Calendar exists"
    )
    resp = client.post("/api/calendars", json={"month": 6, "year": 2026})
    assert resp.status_code == 409


def test_create_calendar_invalid_month(client):
    resp = client.post("/api/calendars", json={"month": 13, "year": 2026})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/calendars/{calendar_id}
# ---------------------------------------------------------------------------


def test_get_calendar_found(client, mock_calendar_service):
    mock_calendar_service.get_calendar.return_value = _make_calendar(id="cal-1")
    resp = client.get("/api/calendars/cal-1")
    assert resp.status_code == 200
    assert resp.json()["id"] == "cal-1"


def test_get_calendar_not_found(client, mock_calendar_service):
    mock_calendar_service.get_calendar.side_effect = CalendarServiceError(
        "calendar_not_found", "Calendar not found"
    )
    resp = client.get("/api/calendars/unknown")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/calendars/{calendar_id}
# ---------------------------------------------------------------------------


def test_delete_calendar_success(client, mock_calendar_service):
    resp = client.delete("/api/calendars/cal-1")
    assert resp.status_code == 204
    mock_calendar_service.soft_delete_calendar.assert_called_once()


def test_delete_calendar_not_found(client, mock_calendar_service):
    mock_calendar_service.soft_delete_calendar.side_effect = CalendarServiceError(
        "calendar_not_found", "Calendar not found"
    )
    resp = client.delete("/api/calendars/unknown")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/calendars/{calendar_id}/approve
# ---------------------------------------------------------------------------


def test_approve_calendar_success(client, mock_calendar_service, engine):
    """Seed a calendar + version in DB so get_latest_version works."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    cal = _make_calendar(id="cal-approve")
    ver = _make_version(calendar_id="cal-approve", id=str(uuid4()))
    sess.add(cal)
    sess.add(ver)
    sess.commit()
    sess.close()

    mock_calendar_service.approve_version.return_value = ver

    resp = client.post("/api/calendars/cal-approve/approve", json={"reason": "Looks good"})
    assert resp.status_code == 200
    assert resp.json()["version_number"] == 1


def test_approve_calendar_no_version(client):
    resp = client.post("/api/calendars/no-version/approve", json={"reason": "ok"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/calendars/{calendar_id}/new-version
# ---------------------------------------------------------------------------


def test_new_version_success(client, mock_calendar_service):
    mock_calendar_service.new_version_after_approval.return_value = _make_version(version_number=2)
    resp = client.post("/api/calendars/cal-1/new-version?reason=fixes")
    assert resp.status_code == 201
    assert resp.json()["version_number"] == 2


def test_new_version_not_found(client, mock_calendar_service):
    mock_calendar_service.new_version_after_approval.side_effect = CalendarServiceError(
        "calendar_not_found", "Not found"
    )
    resp = client.post("/api/calendars/unknown/new-version")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/calendars/{calendar_id}/unlock
# ---------------------------------------------------------------------------


def test_unlock_calendar_success(client, mock_calendar_service):
    mock_calendar_service.unlock_calendar.return_value = _make_version(status="draft")
    resp = client.post("/api/calendars/cal-1/unlock")
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


# ---------------------------------------------------------------------------
# POST /api/calendars/{calendar_id}/generate
# ---------------------------------------------------------------------------


def test_generate_calendar_success(client, mock_generation_service, engine):
    from datetime import date as _date
    from dataclasses import dataclass
    from unittest.mock import PropertyMock

    from backend.app.application.calendars.generation_service import GenerationSummary

    # Mock calendar_repo on the service so route can read calendar status
    mock_repo = MagicMock()
    mock_repo.get_calendar_by_id.return_value = _make_calendar(
        id="cal-gen", status="draft", generation_mode="assisted_auto",
    )
    type(mock_generation_service).calendar_repo = PropertyMock(return_value=mock_repo)

    @dataclass
    class FakeSlotResult:
        slot: object
        assigned_doctor_id: str | None
        score: object | None
        rationale: dict

    @dataclass
    class FakeSlotRequest:
        request_date: _date
        service_area_id: str
        area_weight: float

        @property
        def date(self) -> _date:
            return self.request_date

    slot_request = FakeSlotRequest(request_date=_date(2026, 5, 1), service_area_id="area-1", area_weight=3)
    slot = FakeSlotResult(slot=slot_request, assigned_doctor_id="doc-1", score=None, rationale={})

    summary = GenerationSummary(
        version_id="ver-1",
        calendar_id="cal-gen",
        month=5,
        year=2026,
        total_slots=10,
        assigned_count=8,
        gap_count=2,
        slot_results=[slot],
    )
    mock_generation_service.generate.return_value = summary

    resp = client.post("/api/calendars/cal-gen/generate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_slots"] == 10
    assert data["assigned_count"] == 8
    assert data["gap_count"] == 2


# ---------------------------------------------------------------------------
# POST .../versions/{version_id}/assignments
# ---------------------------------------------------------------------------


def test_assign_doctor_success(client, mock_assignment_service):
    mock_assignment_service.assign_doctor.return_value = _make_assignment(doctor_id="doc-1")

    resp = client.post(
        "/api/calendars/cal-1/versions/ver-1/assignments",
        json={"doctor_id": "doc-1", "service_date": "2026-05-01", "service_area_id": "area-1"},
    )
    assert resp.status_code == 201
    assert resp.json()["doctor_id"] == "doc-1"
    mock_assignment_service.assign_doctor.assert_called_once()


def test_assign_doctor_hard_block(client, mock_assignment_service):
    mock_assignment_service.assign_doctor.side_effect = CalendarServiceError(
        "hard_block", "Doctor not available"
    )
    resp = client.post(
        "/api/calendars/cal-1/versions/ver-1/assignments",
        json={"doctor_id": "doc-1", "service_date": "2026-05-01", "service_area_id": "area-1"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE .../versions/{version_id}/assignments/{assignment_id}
# ---------------------------------------------------------------------------


def test_remove_assignment_success(client, mock_assignment_service):
    resp = client.delete("/api/calendars/cal-1/versions/ver-1/assignments/assign-1")
    assert resp.status_code == 204
    mock_assignment_service.remove_assignment.assert_called_once()


# ---------------------------------------------------------------------------
# PATCH .../versions/{version_id}/assignments/{assignment_id}
# ---------------------------------------------------------------------------


def test_replace_assignment_success(client, mock_assignment_service):
    mock_assignment_service.replace_assignment.return_value = _make_assignment(doctor_id="doc-2")

    resp = client.patch(
        "/api/calendars/cal-1/versions/ver-1/assignments/assign-1",
        json={"doctor_id": "doc-2"},
    )
    assert resp.status_code == 200
    assert resp.json()["doctor_id"] == "doc-2"
