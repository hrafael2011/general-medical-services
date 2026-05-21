"""Tests for auth routes — login, me, change-password, set-password."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.auth import get_account_service
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def user():
    return UserModel(
        id="test-user",
        email="user@test.com",
        password_hash="hash",
        name="Test User",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_account_service():
    return MagicMock()


@pytest.fixture
def client(session, user, mock_account_service):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_account_service] = lambda: mock_account_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers: create a client with pre-seeded data for set-password tests
# ---------------------------------------------------------------------------


def _create_seed_session():
    """Create a fresh engine + session with all tables."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return SessionLocal(), SessionLocal


def _seeded_client(raw_token_str: str) -> tuple[TestClient, str]:
    """Create a TestClient with a pre-seeded set_password token.

    Data is committed BEFORE create_app() to ensure TestClient
    initialization doesn't interfere with session visibility.
    Returns (client, raw_token).
    """
    sess, SessionLocal = _create_seed_session()

    token_hash = sha256(raw_token_str.encode()).hexdigest()
    token = SetPasswordTokenModel(
        id=str(uuid4()),
        user_id="test-user",
        token_hash=token_hash,
        email="user@test.com",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        created_at=datetime.now(UTC),
    )
    sess.add(token)

    user = UserModel(
        id="test-user", email="user@test.com", password_hash="hash",
        name="Test User", role="encargado", active=True,
        must_change_password=False, token_version=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    sess.add(user)
    sess.commit()
    sess.close()

    app = create_app()

    def _get_session():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), raw_token_str


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------


def test_login_success(client, mock_account_service):
    """Returns token and user on valid credentials."""
    mock_user = UserModel(
        id="u1", email="a@b.com", password_hash="hash", name="Dr. A",
        role="encargado", active=True, must_change_password=False,
        token_version=1, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    mock_account_service.authenticate.return_value = MagicMock(
        access_token="token-123",
        user=mock_user,
    )

    resp = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "token-123"
    assert data["user"]["email"] == "a@b.com"


def test_login_invalid_credentials(client, mock_account_service):
    """Returns 401 on wrong password."""
    from backend.app.application.accounts.errors import InvalidCredentialsError

    mock_account_service.authenticate.side_effect = InvalidCredentialsError()

    resp = client.post("/api/auth/login", json={"email": "bad@b.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_locked_account(client, mock_account_service):
    """Returns 423 when account is locked."""
    from backend.app.application.accounts.errors import AccountLockedError

    mock_account_service.authenticate.side_effect = AccountLockedError()

    resp = client.post("/api/auth/login", json={"email": "locked@b.com", "password": "pass"})
    assert resp.status_code == 423


def test_login_inactive_user(client, mock_account_service):
    """Returns 403 when account is inactive."""
    from backend.app.application.accounts.errors import InactiveUserError

    mock_account_service.authenticate.side_effect = InactiveUserError()

    resp = client.post("/api/auth/login", json={"email": "off@b.com", "password": "pass"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------


def test_me_returns_current_user(client, user):
    """Returns the authenticated user's profile."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == user.email
    assert data["name"] == user.name


def test_me_unauthenticated():
    """Returns 401 when no user is authenticated."""
    resp = TestClient(create_app()).get("/api/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/change-password
# ---------------------------------------------------------------------------


def test_change_password_success(client, mock_account_service, user):
    """Returns updated user on successful password change."""
    mock_account_service.change_own_password.return_value = user

    resp = client.post("/api/auth/change-password", json={
        "current_password": "old",
        "new_password": "NewPass123!",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email


def test_change_password_invalid(client, mock_account_service):
    """Returns 400 when current password is wrong."""
    from backend.app.application.accounts.errors import InvalidPasswordChangeError

    mock_account_service.change_own_password.side_effect = InvalidPasswordChangeError()

    resp = client.post("/api/auth/change-password", json={
        "current_password": "wrong",
        "new_password": "NewPass123!",
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/auth/set-password
# ---------------------------------------------------------------------------


def test_validate_set_password_token_valid():
    """Returns user info for a valid token."""
    client, raw_token = _seeded_client("set-pwd-valid-token-123")
    resp = client.get(f"/api/auth/set-password?token={raw_token}")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["email"] == "user@test.com"


def test_validate_set_password_token_invalid(client):
    """Returns valid=False for a bogus token."""
    resp = client.get("/api/auth/set-password?token=bogus-token")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


# ---------------------------------------------------------------------------
# POST /api/auth/set-password
# ---------------------------------------------------------------------------


def test_set_password_success():
    """Sets password successfully with valid token."""
    client, raw_token = _seeded_client("set-pwd-success-token-456")
    resp = client.post("/api/auth/set-password", json={
        "token": raw_token,
        "password": "NewPass123!",
    })
    assert resp.status_code == 200
    assert resp.json()["message"] is not None


def test_set_password_invalid_token(client):
    """Returns 404 for invalid token."""
    resp = client.post("/api/auth/set-password", json={
        "token": "bogus-token",
        "password": "NewPass123!",
    })
    assert resp.status_code == 404


def test_set_password_weak_password(client):
    """Returns 422 for short password (Pydantic validation: min_length=10)."""
    resp = client.post("/api/auth/set-password", json={
        "token": "any-token",
        "password": "short",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password
# ---------------------------------------------------------------------------


def _seed_user(session, **kwargs):
    from backend.app.infrastructure.db.models.user import UserModel as UM

    defaults = {
        "id": "test-user",
        "email": "user@test.com",
        "password_hash": "hash",
        "name": "Test User",
        "role": "encargado",
        "active": True,
        "must_change_password": False,
        "token_version": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    user = UM(**defaults)
    session.add(user)
    session.commit()
    return user


def _make_forgot_password_client(session_factory, user_override=None):
    """Create a TestClient for forgot-password tests with a seeded session."""
    app = create_app()

    def _get_session():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    if user_override is not None:
        app.dependency_overrides[get_current_user] = lambda: user_override
    return TestClient(app)


def test_forgot_password_returns_200_for_known_email():
    """Always returns 200 with a generic message — even if email exists."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    _seed_user(sess)

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "user@test.com"})
    assert resp.status_code == 200
    assert "mensaje" in resp.json()["message"].lower() or "enlace" in resp.json()["message"].lower()


def test_forgot_password_returns_200_for_unknown_email():
    """Returns 200 with same generic message — does NOT reveal whether email exists."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "no-existe@test.com"})
    assert resp.status_code == 200
    assert "mensaje" in resp.json()["message"].lower() or "enlace" in resp.json()["message"].lower()


def test_forgot_password_rate_limit_by_email():
    """Returns 429 after exceeding 3 requests per email in 1 hour."""
    from backend.app.infrastructure.db.models.user import PasswordRecoveryAttemptModel

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    # Pre-seed 3 recovery attempts for the same email
    sess = SessionLocal()
    now = datetime.now(UTC)
    for i in range(3):
        sess.add(PasswordRecoveryAttemptModel(
            id=f"att-{i}",
            email="rate@test.com",
            ip_address=f"192.168.1.{i}",
            attempted_at=now,
        ))
    sess.commit()

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "rate@test.com"})
    assert resp.status_code == 429


def test_forgot_password_rate_limit_by_ip():
    """Returns 429 after exceeding 5 requests per IP in 1 hour."""
    from backend.app.infrastructure.db.models.user import PasswordRecoveryAttemptModel

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    # Pre-seed 5 recovery attempts from the TestClient's IP
    sess = SessionLocal()
    now = datetime.now(UTC)
    for i in range(5):
        sess.add(PasswordRecoveryAttemptModel(
            id=f"att-{i}",
            email=f"user{i}@test.com",
            ip_address="testclient",
            attempted_at=now,
        ))
    sess.commit()

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "new@test.com"})
    assert resp.status_code == 429


def test_forgot_password_creates_token_for_active_user():
    """Creates a set-password token for an active user."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    sess = SessionLocal()
    user = _seed_user(sess, email="active@test.com", active=True)

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "active@test.com"})
    assert resp.status_code == 200

    # Token should have been created for this user
    s2 = SessionLocal()
    tokens = s2.query(SetPasswordTokenModel).filter(
        SetPasswordTokenModel.user_id == user.id,
    ).all()
    assert len(tokens) == 1
    assert tokens[0].email == "active@test.com"
    # Self-service recovery tokens expire in 30 minutes
    expires = tokens[0].expires_at.replace(tzinfo=UTC)
    assert expires <= datetime.now(UTC) + timedelta(minutes=30)


def test_forgot_password_does_not_create_token_for_inactive_user():
    """Does NOT create a token for an inactive user, but still returns 200."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    sess = SessionLocal()
    user = _seed_user(sess, email="inactive@test.com", active=False)

    client = _make_forgot_password_client(SessionLocal)
    resp = client.post("/api/auth/forgot-password", json={"email": "inactive@test.com"})
    assert resp.status_code == 200

    # No token should have been created
    s2 = SessionLocal()
    tokens = s2.query(SetPasswordTokenModel).filter(
        SetPasswordTokenModel.user_id == user.id,
    ).all()
    assert len(tokens) == 0


def test_forgot_password_invalid_email_format(client):
    """Returns 422 for invalid email format."""
    resp = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    assert resp.status_code == 422
