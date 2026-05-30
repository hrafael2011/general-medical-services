"""Tests for availability API routes."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.availability import get_availability_service
from backend.app.application.availability.errors import AvailabilityError
from backend.app.application.availability.service import AvailabilityService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
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
def mock_service():
    return MagicMock(spec=AvailabilityService)


@pytest.fixture
def seed_data(engine):
    """Seed one doctor + one availability record + one restriction."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()

    doctor_id = str(uuid4())
    doctor = DoctorModel(
        id=doctor_id,
        name="Dr. Availability",
        normalized_name="dr. availability",
        sex="male",
        active=True,
        service_active=True,
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        whatsapp_phone="+18095551234",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sess.add(doctor)

    avail = DoctorAvailabilityModel(
        id=str(uuid4()),
        doctor_id=doctor_id,
        availability_type="monthly_variable",
        year=2026,
        month=5,
        available_dates=[1, 15, 20],
        source="manual",
        review_status="approved",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sess.add(avail)

    restriction = DoctorRestrictionModel(
        id=str(uuid4()),
        doctor_id=doctor_id,
        restriction_type="license",
        severity="hard_block",
        starts_at=date(2026, 6, 1),
        ends_at=date(2026, 6, 15),
        source="manual",
        review_status="approved",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sess.add(restriction)

    sess.commit()
    sess.close()
    return {"doctor_id": doctor_id}


@pytest.fixture
def client(session_local, user, seed_data, mock_service):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_availability_service] = lambda: mock_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/availability/doctors/{doctor_id}
# ---------------------------------------------------------------------------


def test_list_availability_returns_records(client, seed_data):
    resp = client.get(f"/api/availability/doctors/{seed_data['doctor_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["availability_type"] == "monthly_variable"


def test_list_availability_empty_for_unknown_doctor(client):
    resp = client.get("/api/availability/doctors/unknown-id")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/availability/doctors/{doctor_id}/restrictions
# ---------------------------------------------------------------------------


def test_list_restrictions_returns_records(client, seed_data):
    resp = client.get(f"/api/availability/doctors/{seed_data['doctor_id']}/restrictions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["restriction_type"] == "license"


def test_list_restrictions_empty_for_unknown_doctor(client):
    resp = client.get("/api/availability/doctors/unknown-id/restrictions")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/availability/available-doctors
# ---------------------------------------------------------------------------


def test_available_doctors_returns_ids(client, mock_service):
    mock_service.get_available_doctor_ids.return_value = ["doc-1", "doc-2"]

    resp = client.get("/api/availability/available-doctors?date=2026-05-14")
    assert resp.status_code == 200
    assert resp.json() == ["doc-1", "doc-2"]
    mock_service.get_available_doctor_ids.assert_called_once_with(date(2026, 5, 14))


# ---------------------------------------------------------------------------
# POST /api/availability/doctors/{doctor_id}/weekly
# ---------------------------------------------------------------------------


def test_set_weekly_success(client, seed_data, mock_service):
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    record = DoctorAvailabilityModel(
        id=str(uuid4()), doctor_id=seed_data["doctor_id"],
        availability_type="weekly", days_of_week=[0, 2],
        source="manual", review_status="approved",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_service.set_weekly_availability.return_value = record

    resp = client.post(
        f"/api/availability/doctors/{seed_data['doctor_id']}/weekly",
        json={"days_of_week": [0, 2]},
    )
    assert resp.status_code == 201
    assert resp.json()["availability_type"] == "weekly"


def test_set_weekly_doctor_not_found(client, mock_service):
    mock_service.set_weekly_availability.side_effect = AvailabilityError(
        "doctor_not_found", "Doctor not found"
    )

    resp = client.post(
        "/api/availability/doctors/unknown/weekly",
        json={"days_of_week": [0]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/availability/doctors/{doctor_id}/monthly
# ---------------------------------------------------------------------------


def test_set_monthly_success(client, seed_data, mock_service):
    record = DoctorAvailabilityModel(
        id=str(uuid4()), doctor_id=seed_data["doctor_id"],
        availability_type="monthly", year=2026, month=6, available_dates=[5, 10, 15],
        source="manual", review_status="approved",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_service.set_monthly_availability.return_value = record

    resp = client.post(
        f"/api/availability/doctors/{seed_data['doctor_id']}/monthly",
        json={"year": 2026, "month": 6, "available_dates": [5, 10, 15]},
    )
    assert resp.status_code == 201
    assert resp.json()["year"] == 2026
    assert resp.json()["month"] == 6


def test_set_monthly_invalid_params(client):
    resp = client.post(
        "/api/availability/doctors/any-id/monthly",
        json={"year": 1999, "month": 6, "available_dates": [5]},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/availability/doctors/any-id/monthly",
        json={"year": 2026, "month": 13, "available_dates": [5]},
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/availability/doctors/any-id/monthly",
        json={"year": 2026, "month": 6, "available_dates": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/availability/doctors/{doctor_id}/recurring
# ---------------------------------------------------------------------------


def test_set_recurring_success(client, seed_data, mock_service):
    record = DoctorAvailabilityModel(
        id=str(uuid4()), doctor_id=seed_data["doctor_id"],
        availability_type="recurring", weekday=1, week_number=2,
        source="manual", review_status="approved",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_service.set_recurring_availability.return_value = record

    resp = client.post(
        f"/api/availability/doctors/{seed_data['doctor_id']}/recurring",
        json={"weekday": 1, "week_number": 2},
    )
    assert resp.status_code == 201
    assert resp.json()["weekday"] == 1
    assert resp.json()["week_number"] == 2


def test_set_recurring_invalid_params(client):
    resp = client.post(
        "/api/availability/doctors/any-id/recurring",
        json={"weekday": 7, "week_number": 2},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/availability/doctors/{doctor_id}/restrictions
# ---------------------------------------------------------------------------


def test_add_restriction_success(client, seed_data, mock_service):
    record = DoctorRestrictionModel(
        id=str(uuid4()), doctor_id=seed_data["doctor_id"],
        restriction_type="restriction", severity="warn",
        starts_at=date(2026, 7, 1),
        source="manual", review_status="approved",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_service.add_restriction.return_value = record

    resp = client.post(
        f"/api/availability/doctors/{seed_data['doctor_id']}/restrictions",
        json={
            "restriction_type": "restriction",
            "severity": "warn",
            "starts_at": "2026-07-01",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["restriction_type"] == "restriction"


def test_add_restriction_invalid_type(client):
    resp = client.post(
        "/api/availability/doctors/any-id/restrictions",
        json={
            "restriction_type": "invalid",
            "severity": "warn",
            "starts_at": "2026-07-01",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/availability/restrictions/{restriction_id}/lift
# ---------------------------------------------------------------------------


def test_lift_restriction_success(client, mock_service):
    record = DoctorRestrictionModel(
        id=str(uuid4()), doctor_id="doc-id",
        restriction_type="restriction", severity="warn",
        starts_at=date(2026, 7, 1),
        source="manual", review_status="approved",
        lifted_at=datetime.now(UTC), lifted_by="test-user",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_service.lift_restriction.return_value = record

    resp = client.post(f"/api/availability/restrictions/{record.id}/lift")
    assert resp.status_code == 200
    assert resp.json()["lifted_by"] == "test-user"
    mock_service.lift_restriction.assert_called_once()


def test_lift_restriction_not_found(client, mock_service):
    mock_service.lift_restriction.side_effect = AvailabilityError(
        "restriction_not_found", "Restriction not found"
    )

    resp = client.post("/api/availability/restrictions/unknown/lift")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/availability/pending
# ---------------------------------------------------------------------------


def test_get_pending_availability_no_pending(client, seed_data):
    """Doctor has monthly availability for May 2026, so no pending."""
    resp = client.get("/api/availability/pending?year=2026&month=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert data["month"] == 5
    assert data["total"] == 0


def test_get_pending_availability_pending_for_different_month(client, seed_data):
    """Doctor submitted for May but we ask about June → should be pending."""
    resp = client.get("/api/availability/pending?year=2026&month=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert seed_data["doctor_id"] in {p["doctor_id"] for p in data["pending"]}


def test_get_pending_availability_invalid_year(client):
    resp = client.get("/api/availability/pending?year=1999&month=5")
    assert resp.status_code == 422
