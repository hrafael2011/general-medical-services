"""Tests for audit API routes — single GET endpoint with real DB."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


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
def admin_user():
    return UserModel(
        id="admin-user", email="admin@test.com", password_hash="hash", name="Admin User",
        role="admin", active=True, must_change_password=False, token_version=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


@pytest.fixture
def seed_data(engine, admin_user):
    """Seed admin user + audit events."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()

    sess.add(admin_user)

    events = []
    for i in range(3):
        event = AuditEventModel(
            id=str(uuid4()),
            actor_id=admin_user.id,
            action_type="create",
            entity_type="doctor",
            entity_id=str(uuid4()),
            occurred_at=datetime.now(UTC),
        )
        sess.add(event)
        events.append(event)

    # Event with different action_type for filtering
    other = AuditEventModel(
        id=str(uuid4()),
        actor_id=admin_user.id,
        action_type="update",
        entity_type="calendar",
        entity_id=str(uuid4()),
        occurred_at=datetime.now(UTC),
    )
    sess.add(other)

    sess.commit()
    sess.close()


@pytest.fixture
def client(session_local, admin_user, seed_data):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/audit
# ---------------------------------------------------------------------------


def test_list_audit_events_returns_all(client):
    resp = client.get("/api/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_list_audit_events_pagination(client):
    resp = client.get("/api/audit?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 4
    assert data["limit"] == 2


def test_list_audit_events_filter_by_action(client):
    resp = client.get("/api/audit?action_type=update")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["action_type"] == "update"


def test_list_audit_events_filter_by_entity(client):
    resp = client.get("/api/audit?entity_type=calendar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["entity_type"] == "calendar"


def test_list_audit_events_no_match(client):
    resp = client.get("/api/audit?action_type=delete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_audit_events_includes_presented_fields(client):
    """actor_display should be resolved from the seeded user."""
    resp = client.get("/api/audit?limit=1")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "Admin User" in item["actor_display"]
    assert item["action_type"] is not None
