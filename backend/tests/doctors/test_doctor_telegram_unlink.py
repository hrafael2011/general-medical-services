"""Desvincular el Telegram de un médico.

Sin esto, un vínculo hecho al médico equivocado no tenía vuelta atrás desde el
sistema: había que tocar `doctors.telegram_chat_id` a mano.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture()
def admin_user(session):
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Admin",
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=["manage_doctors"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture()
def client(session, admin_user):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _doctor_with_telegram(session) -> DoctorModel:
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="DR. VINCULADO",
        normalized_name=f"dr vinculado {uuid.uuid4().hex[:8]}",
        sex="male",
        whatsapp_phone="8091234567",
        telegram_chat_id="555",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(doctor)
    session.commit()
    return doctor


def test_admin_unlinks_a_doctor(client, session):
    doctor = _doctor_with_telegram(session)

    response = client.post(f"/api/doctors/{doctor.id}/unlink-telegram")

    assert response.status_code == 204
    session.refresh(doctor)
    assert doctor.telegram_chat_id is None


def test_the_unlink_is_audited(client, session):
    doctor = _doctor_with_telegram(session)

    client.post(f"/api/doctors/{doctor.id}/unlink-telegram")

    event = session.query(AuditEventModel).filter_by(
        action_type="doctor_updated", entity_id=doctor.id
    ).one()
    assert event.after_snapshot == {"telegram_chat_id": None}


def test_an_unknown_doctor_returns_404(client):
    response = client.post("/api/doctors/no-existe/unlink-telegram")

    assert response.status_code == 404
