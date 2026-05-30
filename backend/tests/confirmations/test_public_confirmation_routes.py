import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import action_alerts as _action_alerts  # noqa: F401
from backend.app.infrastructure.db.models import audit as _audit  # noqa: F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: F401
from backend.app.infrastructure.db.models import confirmations as _confirmations  # noqa: F401
from backend.app.infrastructure.db.models import missions as _missions  # noqa: F401
from backend.app.infrastructure.db.models import notifications as _notifications  # noqa: F401
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: F401
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
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


def _client(db_session) -> TestClient:
    app = create_app()

    def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    return TestClient(app)


def _doctor(db_session, *, name: str = "Dra. Confirmable") -> DoctorModel:
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name=name,
        normalized_name=" ".join(name.strip().lower().split()),
        sex="female",
        rank_id=None,
        department_id=None,
        notes=None,
        active=True,
        service_active=True,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=6,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deactivated_at=None,
        deactivated_by=None,
    )
    db_session.add(doctor)
    db_session.flush()
    return doctor


def test_public_confirmation_preview_does_not_require_login_or_expose_ids(session) -> None:
    doctor = _doctor(session)
    service = ConfirmationRequestService(ConfirmationRequestRepository(session))
    request = service.create_request(
        confirmation_type="mission",
        idempotency_key="mission:public-preview",
        doctor_id=doctor.id,
        mission_id="mission-secret-id",
    )
    session.commit()

    response = _client(session).get(f"/api/confirmation-requests/public/{request.response_token}")

    assert response.status_code == 200
    data = response.json()
    assert data["confirmation_type"] == "mission"
    assert data["status"] == "pending"
    assert data["doctor_name"] == doctor.name
    assert "doctor_id" not in data
    assert "response_token" not in data
    assert "mission_id" not in data


def test_public_confirmation_confirm_marks_request_confirmed(session) -> None:
    doctor = _doctor(session)
    service = ConfirmationRequestService(ConfirmationRequestRepository(session))
    request = service.create_request(
        confirmation_type="service",
        idempotency_key="service:public-confirm",
        doctor_id=doctor.id,
        assignment_id="assignment-secret-id",
    )
    session.commit()

    response = _client(session).post(
        f"/api/confirmation-requests/public/{request.response_token}/confirm",
        json={"note": "Confirmo disponibilidad"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    refreshed = ConfirmationRequestRepository(session).get_by_id(request.id)
    assert refreshed is not None
    assert refreshed.status == "confirmed"
    assert refreshed.response_channel == "public_link"
    assert refreshed.response_payload == {
        "action": "confirm",
        "note": "Confirmo disponibilidad",
    }


def test_public_confirmation_invalid_token_returns_404(session) -> None:
    response = _client(session).post(
        "/api/confirmation-requests/public/token-inexistente/confirm",
        json={},
    )

    assert response.status_code == 404


def test_public_confirmation_decline_is_not_available(session) -> None:
    doctor = _doctor(session)
    service = ConfirmationRequestService(ConfirmationRequestRepository(session))
    request = service.create_request(
        confirmation_type="service",
        idempotency_key="service:public-decline-disabled",
        doctor_id=doctor.id,
        assignment_id="assignment-secret-id",
    )
    session.commit()

    response = _client(session).post(
        f"/api/confirmation-requests/public/{request.response_token}/decline",
        json={"note": "No puedo"},
    )

    assert response.status_code == 404
    refreshed = ConfirmationRequestRepository(session).get_by_id(request.id)
    assert refreshed is not None
    assert refreshed.status == "pending"
