"""Revocar el canal de avisos de un usuario.

`users.telegram_chat_id` es lo que lee el job de notificaciones. La pantalla de
Telegram solo podía desactivar el vínculo del **asistente**
(`telegram_user_links`), que es otro campo: un admin no tenía forma de cortar los
avisos, y un error de vinculación solo se corregía tocando la base.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.models.audit import AuditEventModel
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
        permissions=["manage_telegram"],
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


def _make_user(session, *, telegram_chat_id: str | None) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Encargado",
        email=f"enc-{uuid.uuid4().hex[:8]}@example.com",
        role="encargado",
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=["receive_escalation_alerts"],
        telegram_chat_id=telegram_chat_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def test_admin_revokes_the_alerts_channel(client, session):
    user = _make_user(session, telegram_chat_id="555")

    response = client.post(f"/api/telegram/users/{user.id}/revoke-alerts")

    assert response.status_code == 204
    session.refresh(user)
    assert user.telegram_chat_id is None


def test_the_revocation_is_audited(client, session):
    user = _make_user(session, telegram_chat_id="555")

    client.post(f"/api/telegram/users/{user.id}/revoke-alerts")

    event = session.query(AuditEventModel).filter_by(
        action_type="user_updated", entity_id=user.id
    ).one()
    assert event.before_snapshot == {"telegram_chat_id": "555"}
    assert event.after_snapshot == {"telegram_chat_id": None}


def test_an_unknown_user_returns_404(client):
    response = client.post("/api/telegram/users/no-existe/revoke-alerts")

    assert response.status_code == 404
