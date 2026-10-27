"""Quién puede generar un enlace de vínculo al bot de avisos.

El listado de admins es solo-superadmin, pero el endpoint aceptaba cualquier
`user_id`: la política existía en la pantalla y no en la API.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture(autouse=True)
def _alerts_bot(monkeypatch):
    """Sin username del bot de avisos el endpoint responde 503 en vez de crear el token."""
    monkeypatch.setattr(
        settings, "telegram_notification_bot_username", "TurnosMedicosNotificaciones_bot"
    )


def _user(session, *, role: str, is_superadmin: bool = False) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name=f"{role} {uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=[],
        is_superadmin=is_superadmin,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _client(session, actor: UserModel) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app)


def test_an_admin_can_generate_a_link_for_an_encargado(session):
    admin = _user(session, role="admin")
    encargado = _user(session, role="encargado")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": encargado.id}
    )

    assert response.status_code == 201
    assert response.json()["deep_link_url"].startswith("https://t.me/")


def test_an_admin_can_generate_their_own_link(session):
    admin = _user(session, role="admin")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": admin.id}
    )

    assert response.status_code == 201


def test_an_admin_cannot_generate_a_link_for_another_admin(session):
    admin = _user(session, role="admin")
    other = _user(session, role="admin")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": other.id}
    )

    assert response.status_code == 403


def test_a_superadmin_can_generate_a_link_for_another_admin(session):
    superadmin = _user(session, role="admin", is_superadmin=True)
    other = _user(session, role="admin")

    response = _client(session, superadmin).post(
        "/api/telegram/link-tokens", json={"user_id": other.id}
    )

    assert response.status_code == 201
