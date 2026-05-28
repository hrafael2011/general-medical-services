import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.application.accounts.service import AccountService
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
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.main import create_app
from backend.app.core.config import settings


@pytest.fixture()
def session():
    # StaticPool ensures all connections share the same in-memory SQLite database,
    # which is necessary because FastAPI runs sync route handlers in a thread pool.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def admin_user(session):
    service = AccountService(UserRepository(session))
    result = service.ensure_admin_password(
        email="admin@example.com",
        name="Admin Test",
        temporary_password="Temporary123!",
    )
    # Change password so must_change_password=False (required by _require_admin check)
    service.change_own_password(
        user=result.user,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    session.commit()
    result.user.is_superadmin = True
    session.commit()
    return result.user


@pytest.fixture()
def client(session, admin_user):
    app = create_app()

    # get_db_session is a generator dependency — override must also yield
    def override_get_db_session():
        yield session

    # The route imports get_db_session from backend.app.infrastructure.db.session
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


def _create_user(session, *, role: str) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name=f"Usuario {role}",
        email=f"{role}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        failed_login_count=0,
        locked_until=None,
        last_login_at=None,
        password_changed_at=None,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deactivated_at=None,
        deactivated_by=None,
    )
    session.add(user)
    session.flush()
    return user


def test_list_users_returns_200(client):
    # GET /api/admin/users — default role filter is "encargado"
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_encargado_returns_201(client):
    response = client.post(
        "/api/admin/users/encargados",
        json={
            "name": "Encargado Test",
            "email": "encargado@example.com",
            "temporary_password": "TempEnc123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "encargado@example.com"
    assert data["user"]["role"] == "encargado"
    assert "temporary_password" in data


def test_create_encargado_duplicate_email_returns_409(client):
    payload = {
        "name": "Enc",
        "email": "dup@example.com",
        "temporary_password": "TempEnc123!",
    }
    client.post("/api/admin/users/encargados", json=payload)
    response = client.post("/api/admin/users/encargados", json=payload)
    assert response.status_code == 409


def test_create_encargado_deleted_email_returns_actionable_409(client, session):
    deleted_user = _create_user(session, role="encargado")
    deleted_user.email = "deleted@example.com"
    deleted_user.deleted_at = datetime.now(UTC)
    session.commit()

    response = client.post(
        "/api/admin/users/encargados",
        json={
            "name": "Nuevo Encargado",
            "email": "deleted@example.com",
            "temporary_password": "TempEnc123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "email_belongs_to_deleted_user",
        "message": "Este correo pertenece a un usuario eliminado. Usa otro correo o restaura el usuario eliminado.",
    }


def test_reset_encargado_password_returns_200(client):
    # Create an encargado first
    create_resp = client.post(
        "/api/admin/users/encargados",
        json={
            "name": "Reset Target",
            "email": "reset@example.com",
            "temporary_password": "TempEnc123!",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["user"]["id"]

    response = client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"temporary_password": "NewTemp456!"},
    )
    assert response.status_code == 200
    assert response.json()["temporary_password"] == "NewTemp456!"


def test_reset_nonexistent_user_returns_404(client):
    response = client.post(
        "/api/admin/users/nonexistent-uuid/reset-password",
        json={"temporary_password": "NewTemp456!"},
    )
    assert response.status_code == 404


@pytest.mark.skipif(not settings.feature_telegram, reason="Telegram feature disabled")
def test_telegram_link_token_allows_encargado(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.post(
        "/api/telegram/link-tokens",
        json={"user_id": user.id},
    )

    assert response.status_code == 201
    assert response.json()["deep_link_url"]


@pytest.mark.skipif(not settings.feature_telegram, reason="Telegram feature disabled")
def test_telegram_link_token_rejects_non_internal_role(client, session):
    user = _create_user(session, role="doctor")
    session.commit()

    response = client.post(
        "/api/telegram/link-tokens",
        json={"user_id": user.id},
    )

    assert response.status_code == 400


@pytest.mark.skipif(not settings.feature_telegram, reason="Telegram feature disabled")
def test_telegram_manual_link_rejects_non_internal_role(client, session):
    user = _create_user(session, role="doctor")
    session.commit()

    response = client.post(
        "/api/telegram/links",
        json={
            "telegram_user_id": "123456",
            "telegram_username": "doctoruser",
            "user_id": user.id,
        },
    )

    assert response.status_code == 400


def test_delete_user_returns_204(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.delete(f"/api/admin/users/{user.id}")
    assert response.status_code == 204

    list_resp = client.get("/api/admin/users")
    assert list_resp.status_code == 200
    user_ids = [u["id"] for u in list_resp.json()]
    assert user.id not in user_ids


def test_delete_nonexistent_user_returns_404(client):
    response = client.delete("/api/admin/users/nonexistent-uuid")
    assert response.status_code == 404


def test_update_user_name_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"name": "Nuevo Nombre"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nuevo Nombre"


def test_update_user_role_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_update_user_active_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"active": False},
    )
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_update_nonexistent_user_returns_404(client):
    response = client.patch(
        "/api/admin/users/nonexistent-uuid",
        json={"name": "Ghost"},
    )
    assert response.status_code == 404
