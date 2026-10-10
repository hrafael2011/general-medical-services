"""Tests for a user editing their own account.

The name is the only self-service field because it is what the weekly list PDF prints
as the left signature, and the change must leave an auditable trace.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.api.dependencies import get_current_user
from backend.app.application.accounts.service import AccountService
from backend.app.application.audit.service import AuditService
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.main import create_app


@pytest.fixture
def user(db_session) -> UserModel:
    account = UserModel(
        id="self-user",
        email="self@test.com",
        password_hash="hash",
        name="Nombre Viejo",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(account)
    db_session.commit()
    return account


def _client(session_local, current_user) -> TestClient:
    app = create_app()

    def _get_session():
        session = session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def test_update_own_profile_changes_the_name(db_session, user) -> None:
    service = AccountService(
        UserRepository(db_session), audit=AuditService(AuditRepository(db_session))
    )

    service.update_own_profile(user=user, name="  DRA. ALEXANDRA ACOSTA  ")
    db_session.commit()

    assert user.name == "DRA. ALEXANDRA ACOSTA"


def test_update_own_profile_audits_before_and_after(db_session, user) -> None:
    service = AccountService(
        UserRepository(db_session), audit=AuditService(AuditRepository(db_session))
    )

    service.update_own_profile(user=user, name="Nombre Nuevo")
    db_session.commit()

    event = db_session.scalars(
        select(AuditEventModel).where(AuditEventModel.action_type == "user_updated")
    ).one()
    assert event.actor_id == user.id  # their own action, not an admin's
    assert event.before_snapshot == {"name": "Nombre Viejo"}
    assert event.after_snapshot == {"name": "Nombre Nuevo"}


def test_update_own_profile_with_the_same_name_writes_nothing(db_session, user) -> None:
    service = AccountService(
        UserRepository(db_session), audit=AuditService(AuditRepository(db_session))
    )

    service.update_own_profile(user=user, name="Nombre Viejo")
    db_session.commit()

    events = db_session.scalars(select(AuditEventModel)).all()
    assert events == []


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


def test_patch_me_updates_the_name(session_local, user) -> None:
    client = _client(session_local, user)

    resp = client.patch("/api/auth/me", json={"name": "DRA. ALEXANDRA ACOSTA"})

    assert resp.status_code == 200
    assert resp.json()["name"] == "DRA. ALEXANDRA ACOSTA"


def test_patch_me_ignores_privilege_fields(session_local, user) -> None:
    """Email, role and permissions are not self-service, even if they are sent."""
    client = _client(session_local, user)

    resp = client.patch(
        "/api/auth/me",
        json={
            "name": "Nombre Nuevo",
            "email": "otro@test.com",
            "role": "admin",
            "permissions": ["manage_users"],
            "is_superadmin": True,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Nombre Nuevo"
    assert body["email"] == "self@test.com"
    assert body["role"] == "encargado"
    assert body["permissions"] == []
    assert body["is_superadmin"] is False


def test_patch_me_rejects_an_empty_name(session_local, user) -> None:
    client = _client(session_local, user)

    assert client.patch("/api/auth/me", json={"name": ""}).status_code == 422
