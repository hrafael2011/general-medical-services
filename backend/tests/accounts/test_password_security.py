"""Tests for password security — history checks, email masking, rate limiting."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.auth import get_account_service
from backend.app.application.accounts.errors import InvalidPasswordChangeError
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.user import (
    LoginAttemptModel,
    PasswordHistoryModel,
    UserModel,
)
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.main import create_app


# ═══════════════════════════════════════════════════════════════════════════
# Service-level tests — password history in change_own_password
# ═══════════════════════════════════════════════════════════════════════════


def test_change_own_password_history_blocks_reuse(db_session) -> None:
    """Set password A, change to B, then try to change to B again → should fail."""
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user
    db_session.commit()

    # First change: Temporary123! → Permanent123!
    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    db_session.commit()

    # Try to reuse the SAME password (Permanent123!) — both the
    # "same as current" check and history check should block it.
    with pytest.raises(InvalidPasswordChangeError):
        service.change_own_password(
            user=admin,
            current_password="Permanent123!",
            new_password="Permanent123!",
        )


def test_change_own_password_history_blocks_past_password(db_session) -> None:
    """Change password multiple times, then try to reuse an older one → should fail."""
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user
    db_session.commit()

    # Change A → B
    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    db_session.commit()

    # Change B → C (C is saved to history along with B)
    service.change_own_password(
        user=admin,
        current_password="Permanent123!",
        new_password="AnotherPass456!",
    )
    db_session.commit()

    # Try to reuse B (Permanent123!) which is in history → should fail
    with pytest.raises(InvalidPasswordChangeError):
        service.change_own_password(
            user=admin,
            current_password="AnotherPass456!",
            new_password="Permanent123!",
        )


def test_change_own_password_allows_new_password(db_session) -> None:
    """Set password A, then change to password B → should succeed."""
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user
    db_session.commit()

    result = service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    assert result is not None
    assert result.password_changed_at is not None


# ═══════════════════════════════════════════════════════════════════════════
# Helpers: shared database setup for API-level tests
# ═══════════════════════════════════════════════════════════════════════════


def _make_shared_db():
    """Create a shared in-memory SQLite engine + SessionLocal for API tests."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    return engine, SessionLocal


def _create_client(SessionLocal):
    """Create a TestClient with a given SessionLocal override."""
    app = create_app()

    def _get_session():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    return TestClient(app)


def _seed_user_and_token(SessionLocal, raw_token: str, **overrides):
    """Seed a user + set-password token, return (user, token, raw_token)."""
    sess = SessionLocal()

    user_kwargs = {
        "id": "test-user",
        "email": "user@test.com",
        "password_hash": "initial-hash",
        "name": "Test User",
        "role": "encargado",
        "active": True,
        "must_change_password": True,
        "token_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    user_kwargs.update(overrides)
    user = UserModel(**user_kwargs)
    sess.add(user)

    token_hash = sha256(raw_token.encode()).hexdigest()
    token = SetPasswordTokenModel(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        email=user.email,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        created_at=datetime.now(UTC),
        created_by=user.id,
    )
    sess.add(token)
    sess.commit()
    sess.close()

    return user, token, raw_token


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/auth/set-password — email masking
# ═══════════════════════════════════════════════════════════════════════════


def test_validate_set_password_token_returns_masked_email():
    """Valid token returns masked email like 'u***@test.com'."""
    _, SessionLocal = _make_shared_db()
    _seed_user_and_token(SessionLocal, "mask-email-token")
    client = _create_client(SessionLocal)

    resp = client.get("/api/auth/set-password?token=mask-email-token")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["email"] == "u***r@test.com"
    assert data["name"] == "Test User"
    assert data["expires_at"] is not None


def test_validate_set_password_token_invalid_token():
    """Bogus token returns valid=False."""
    _, SessionLocal = _make_shared_db()
    client = _create_client(SessionLocal)

    resp = client.get("/api/auth/set-password?token=bogus-token")
    assert resp.status_code == 200
    assert resp.json() == {"valid": False, "email": None, "name": None, "expires_at": None}


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/auth/set-password — password history
# ═══════════════════════════════════════════════════════════════════════════


def test_set_password_history_blocks_reuse():
    """Use token A to set password, then use token B to try the same password → 400."""
    import uuid

    _, SessionLocal = _make_shared_db()

    # Seed one user and two valid tokens
    sess = SessionLocal()
    user = UserModel(
        id="test-user",
        email="user@test.com",
        password_hash="initial-hash",
        name="Test User",
        role="encargado",
        active=True,
        must_change_password=True,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sess.add(user)

    for raw_token_str in ("token-a-history", "token-b-history"):
        token_hash = sha256(raw_token_str.encode()).hexdigest()
        token = SetPasswordTokenModel(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=token_hash,
            email=user.email,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            created_at=datetime.now(UTC),
            created_by=user.id,
        )
        sess.add(token)

    sess.commit()
    sess.close()

    client = _create_client(SessionLocal)

    # First request: set password via token-a
    resp1 = client.post("/api/auth/set-password", json={
        "token": "token-a-history",
        "password": "HistoryTest99!",
    })
    assert resp1.status_code == 200

    # Second request: try same password via token-b
    resp2 = client.post("/api/auth/set-password", json={
        "token": "token-b-history",
        "password": "HistoryTest99!",
    })
    assert resp2.status_code == 400
    assert "reutilizar" in resp2.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/auth/set-password — rate limiting
# ═══════════════════════════════════════════════════════════════════════════


def test_set_password_rate_limited():
    """Returns 429 after 5+ rapid requests with invalid tokens."""
    _, SessionLocal = _make_shared_db()
    client = _create_client(SessionLocal)

    for i in range(5):
        resp = client.post("/api/auth/set-password", json={
            "token": f"invalid-token-{i}",
            "password": "NewPass123!",
        })
        assert resp.status_code == 404, f"Request {i} should be 404, got {resp.status_code}"

    # 6th request should be rate limited
    resp = client.post("/api/auth/set-password", json={
        "token": "invalid-token-6",
        "password": "NewPass123!",
    })
    assert resp.status_code == 429
    assert "Intenta de nuevo" in resp.json()["detail"]


def test_set_password_rate_limit_respects_window():
    """Old attempts outside the 15-min window should not count."""
    _, SessionLocal = _make_shared_db()

    # Seed 5 attempts that are 16 minutes old (outside the 15-min window)
    sess = SessionLocal()
    old_time = datetime.now(UTC) - timedelta(minutes=16)
    for i in range(5):
        sess.add(LoginAttemptModel(
            id=f"old-attempt-{i}",
            ip_address="testclient",
            attempted_at=old_time,
            success=False,
        ))
    sess.commit()
    sess.close()

    client = _create_client(SessionLocal)

    # Should NOT be rate limited (old attempts are pruned)
    resp = client.post("/api/auth/set-password", json={
        "token": "bogus-token",
        "password": "NewPass123!",
    })
    assert resp.status_code == 404  # Invalid token, not rate limited


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/auth/set-password — full success flow
# ═══════════════════════════════════════════════════════════════════════════


def test_set_password_full_success():
    """Complete set-password flow: valid token → password is set and persisted."""
    _, SessionLocal = _make_shared_db()
    user, token, raw_token = _seed_user_and_token(SessionLocal, "success-token")
    client = _create_client(SessionLocal)

    resp = client.post("/api/auth/set-password", json={
        "token": raw_token,
        "password": "NewPass123!",
    })
    assert resp.status_code == 200

    # Verify the password hash was updated in the database
    sess = SessionLocal()
    updated_user = sess.query(UserModel).filter(UserModel.id == user.id).first()
    assert updated_user is not None
    assert updated_user.password_hash != "initial-hash"
    assert updated_user.must_change_password is False

    # Verify password history was recorded
    history = sess.query(PasswordHistoryModel).filter(
        PasswordHistoryModel.user_id == user.id,
    ).all()
    assert len(history) >= 1
    sess.close()
