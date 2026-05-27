"""Tests for doctors API routes — real DB for GET, mocked service for mutations."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.doctors import get_doctor_service
from backend.app.application.doctors.errors import DoctorServiceError
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.db.base import Base
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
def seed_doctor(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    doctor_id = str(uuid4())
    doctor = DoctorModel(
        id=doctor_id,
        name="Dr. Test",
        normalized_name="dr. test",
        sex="male",
        rank_id=None,
        department_id=None,
        whatsapp_phone="123456789",
        notes=None,
        active=True,
        service_active=True,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sess.add(doctor)
    sess.commit()
    sess.close()
    return doctor_id


@pytest.fixture
def mock_service():
    return MagicMock(spec=DoctorService)


@pytest.fixture
def client(session_local, user, seed_doctor, mock_service):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_doctor_service] = lambda: mock_service
    return TestClient(app)


def _make_doctor(**overrides) -> DoctorModel:
    fields = dict(
        id=str(uuid4()), first_name=None, last_name=None,
        name="Dr. Default", normalized_name="dr. default", sex="male",
        rank_id=None, department_id=None, notes=None,
        active=True, service_active=True, service_inactive_reason_id=None,
        service_inactive_detail=None, participa_misiones=True, whatsapp_phone="+18095551234",
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    fields.update(overrides)
    return DoctorModel(**fields)


# ---------------------------------------------------------------------------
# GET /api/doctors
# ---------------------------------------------------------------------------


def test_list_doctors_returns_all(client, seed_doctor):
    resp = client.get("/api/doctors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    names = [d["name"] for d in data["items"]]
    assert "Dr. Test" in names


def test_list_doctors_active_only(client, seed_doctor):
    resp = client.get("/api/doctors?active_only=true")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ---------------------------------------------------------------------------
# GET /api/doctors/{doctor_id}
# ---------------------------------------------------------------------------


def test_get_doctor_found(client, seed_doctor):
    resp = client.get(f"/api/doctors/{seed_doctor}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Dr. Test"
    assert resp.json()["sex"] == "male"


def test_get_doctor_not_found(client):
    resp = client.get("/api/doctors/nonexistent-id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Médico no encontrado."


# ---------------------------------------------------------------------------
# POST /api/doctors
# ---------------------------------------------------------------------------


def test_create_doctor_success(client, mock_service):
    mock_service.create_doctor.return_value = _make_doctor(
        first_name="Juan",
        last_name="Pérez",
        name="Juan Pérez",
    )

    resp = client.post(
        "/api/doctors",
        json={"first_name": "Juan", "last_name": "Pérez", "sex": "male", "whatsapp_phone": "+18095551234"},
    )
    assert resp.status_code == 201
    assert resp.json()["first_name"] == "Juan"
    assert resp.json()["last_name"] == "Pérez"
    assert resp.json()["name"] == "Juan Pérez"
    mock_service.create_doctor.assert_called_once()
    assert mock_service.create_doctor.call_args.kwargs["first_name"] == "Juan"
    assert mock_service.create_doctor.call_args.kwargs["last_name"] == "Pérez"


def test_create_doctor_invalid_sex(client):
    resp = client.post("/api/doctors", json={"name": "Dr. Bad", "sex": "other"})
    assert resp.status_code == 422


def test_create_doctor_empty_name(client):
    resp = client.post("/api/doctors", json={"name": "", "sex": "male"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/doctors/{doctor_id}
# ---------------------------------------------------------------------------


def test_update_doctor_success(client, mock_service):
    mock_service.update_doctor.return_value = _make_doctor(
        first_name="Ana",
        last_name="García",
        name="Ana García",
    )

    resp = client.patch(
        "/api/doctors/some-id",
        json={"first_name": "Ana", "last_name": "García"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Ana"
    assert resp.json()["last_name"] == "García"
    assert resp.json()["name"] == "Ana García"
    mock_service.update_doctor.assert_called_once()


def test_update_doctor_not_found(client, mock_service):
    mock_service.update_doctor.side_effect = DoctorServiceError("doctor_not_found", "Doctor not found")

    resp = client.patch("/api/doctors/non-existent", json={"name": "Dr. Ghost"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "doctor_not_found"


def test_update_doctor_service_error(client, mock_service):
    mock_service.update_doctor.side_effect = DoctorServiceError("some_error", "Bad request")

    resp = client.patch("/api/doctors/some-id", json={"monthly_service_max": -1})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/doctors/{doctor_id}/deactivate-service
# ---------------------------------------------------------------------------


def test_deactivate_service_success(client, mock_service):
    mock_service.deactivate_service.return_value = _make_doctor(
        service_active=False,
        service_inactive_reason_id="reason-1",
        service_inactive_detail="Sick leave",
    )

    resp = client.post("/api/doctors/some-id/deactivate-service", json={"reason_id": "reason-1"})
    assert resp.status_code == 200
    assert resp.json()["service_active"] is False
    mock_service.deactivate_service.assert_called_once()


def test_deactivate_service_not_found(client, mock_service):
    mock_service.deactivate_service.side_effect = DoctorServiceError("doctor_not_found", "Doctor not found")

    resp = client.post("/api/doctors/non-existent/deactivate-service", json={"reason_id": "r1"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/doctors/{doctor_id}/reactivate-service
# ---------------------------------------------------------------------------


def test_reactivate_service_success(client, mock_service):
    mock_service.reactivate_service.return_value = _make_doctor(service_active=True)

    resp = client.post("/api/doctors/some-id/reactivate-service")
    assert resp.status_code == 200
    assert resp.json()["service_active"] is True
    mock_service.reactivate_service.assert_called_once()


def test_reactivate_service_not_found(client, mock_service):
    mock_service.reactivate_service.side_effect = DoctorServiceError("doctor_not_found", "Doctor not found")

    resp = client.post("/api/doctors/non-existent/reactivate-service")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/doctors/{doctor_id}
# ---------------------------------------------------------------------------


def test_delete_doctor_success(client, mock_service):
    mock_service.soft_delete_doctor.return_value = None

    resp = client.delete("/api/doctors/some-id")
    assert resp.status_code == 204
    mock_service.soft_delete_doctor.assert_called_once_with("some-id", actor_id="test-user")


def test_delete_doctor_not_found(client, mock_service):
    mock_service.soft_delete_doctor.side_effect = DoctorServiceError(
        "doctor_not_found", "Doctor with id non-existent not found"
    )

    resp = client.delete("/api/doctors/non-existent")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "doctor_not_found"
