from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.application.accounts.invitation_service import (
    InvitationService,
    _hash_token,
)
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.user import UserModel


@pytest.fixture
def mock_token_repo():
    return MagicMock()


@pytest.fixture
def service(mock_token_repo):
    return InvitationService(mock_token_repo)


@pytest.fixture
def user():
    return UserModel(
        id=str(uuid4()),
        name="Test User",
        email="test@example.com",
        role="encargado",
        active=True,
    )


@pytest.fixture
def admin():
    return UserModel(
        id=str(uuid4()),
        name="Admin",
        email="admin@test.com",
        role="admin",
        active=True,
    )


@patch("backend.app.application.accounts.invitation_service.send_email")
def test_create_invitation_sends_email(mock_send, service, user, admin):
    raw_token = service.create_invitation(user=user, created_by=admin)
    assert len(raw_token) > 0
    mock_send.assert_called_once()
    assert mock_send.call_args[1]["to"] == user.email
    assert "Invitación" in mock_send.call_args[1]["subject"]
    assert raw_token in mock_send.call_args[1]["html"]


@patch("backend.app.application.accounts.invitation_service.send_email")
def test_create_reset_sends_email(mock_send, service, user, admin):
    raw_token = service.create_reset(user=user, created_by=admin)
    assert len(raw_token) > 0
    mock_send.assert_called_once()
    assert "Restablecer" in mock_send.call_args[1]["subject"]


@patch("backend.app.application.accounts.invitation_service.send_email")
def test_create_invitation_stores_hash(mock_send, service, mock_token_repo, user, admin):
    raw_token = service.create_invitation(user=user, created_by=admin)
    # Verify add was called with a token record
    mock_token_repo.add.assert_called_once()
    token_record = mock_token_repo.add.call_args[0][0]
    assert token_record.user_id == user.id
    assert token_record.email == user.email
    # Verify the hash matches
    assert _hash_token(raw_token) == token_record.token_hash
    assert token_record.expires_at > datetime.now(UTC)


@patch("backend.app.application.accounts.invitation_service.send_email")
def test_validate_token_returns_none_for_invalid(mock_send, service, mock_token_repo):
    mock_token_repo.list_valid.return_value = []
    result = service.validate_token("invalid-token")
    assert result is None


def test_validate_token_found(service, mock_token_repo, user, admin):
    raw_token = "test-raw-token-value-12345"
    hashed = _hash_token(raw_token)

    token_record = SetPasswordTokenModel(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=hashed,
        email=user.email,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
        used_at=None,
        created_by=admin.id,
        created_at=datetime.now(UTC),
    )
    mock_token_repo.list_valid.return_value = [token_record]

    result = service.validate_token(raw_token)
    assert result is not None
    assert result.email == user.email


def test_validate_token_wrong_hash(service, mock_token_repo, user, admin):
    """Should return None when hash doesn't match."""
    token_record = SetPasswordTokenModel(
        id=str(uuid4()),
        user_id=user.id,
        token_hash=_hash_token("different-token"),
        email=user.email,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
        used_at=None,
        created_by=admin.id,
        created_at=datetime.now(UTC),
    )
    mock_token_repo.list_valid.return_value = [token_record]

    result = service.validate_token("wrong-token")
    assert result is None


def test_mark_used_sets_timestamp(service, mock_token_repo, user, admin):
    token_record = SetPasswordTokenModel(
        id=str(uuid4()),
        user_id=user.id,
        token_hash="hash",
        email=user.email,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
        used_at=None,
        created_by=admin.id,
        created_at=datetime.now(UTC),
    )
    assert token_record.used_at is None
    service.mark_used(token_record)
    assert token_record.used_at is not None


def test_hash_token_consistency():
    """Same token always produces same hash."""
    token = "my-test-token-123"
    assert _hash_token(token) == _hash_token(token)


def test_hash_token_different():
    """Different tokens produce different hashes."""
    assert _hash_token("token-a") != _hash_token("token-b")
