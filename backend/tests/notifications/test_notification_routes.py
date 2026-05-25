"""Tests for notifications API routes."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.api.routes.notifications import get_notification_service
from backend.app.application.notifications.service import NotificationService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app
from backend.app.core.config import settings


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
def mock_service():
    return MagicMock(spec=NotificationService)


@pytest.fixture
def seed_data(engine):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()

    for typ in ("reminder", "confirmation"):
        notif = NotificationEventModel(
            id=str(uuid4()),
            notification_type=typ,
            status="pending",
            idempotency_key=f"key-{typ}-{uuid4()}",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        sess.add(notif)

    sess.commit()
    sess.close()


@pytest.fixture
def client(session_local, user, seed_data, mock_service):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_notification_service] = lambda: mock_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/notifications
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not settings.feature_notifications, reason="Notifications feature disabled")
def test_list_notifications_returns_all(client):
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.skipif(not settings.feature_notifications, reason="Notifications feature disabled")
def test_list_notifications_filter_by_type(client):
    resp = client.get("/api/notifications?notification_type=reminder")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["notification_type"] == "reminder"


@pytest.mark.skipif(not settings.feature_notifications, reason="Notifications feature disabled")
def test_list_notifications_no_match(client):
    resp = client.get("/api/notifications?notification_type=unknown")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# POST /api/notifications/process
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not settings.feature_notifications, reason="Notifications feature disabled")
def test_process_notifications_success(client, mock_service):
    mock_service.process_pending.return_value = {"sent": 2, "failed": 0, "skipped": 1, "errors": []}

    resp = client.post("/api/notifications/process")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sent"] == 2
    assert data["failed"] == 0
    assert data["skipped"] == 1
    mock_service.process_pending.assert_called_once()
