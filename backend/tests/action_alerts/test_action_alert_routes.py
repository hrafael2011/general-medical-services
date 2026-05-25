"""Tests for action-alerts API routes — all use real DB."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel
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
def user():
    return UserModel(
        id="test-user", email="user@test.com", password_hash="hash", name="Test User",
        role="admin", active=True, must_change_password=False, token_version=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


@pytest.fixture
def seed_data(engine, user):
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    sess.add(user)

    alert_ids = []
    for sev in ("critical", "warning", "info"):
        alert = ActionAlertModel(
            id=str(uuid4()),
            alert_type="coverage_gap",
            section="calendars",
            severity=sev,
            status="open",
            title=f"Alert {sev}",
            message=f"Test {sev} alert",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        sess.add(alert)
        alert_ids.append(alert.id)

    # A resolved alert (shouldn't appear in default open filter)
    resolved = ActionAlertModel(
        id=str(uuid4()),
        alert_type="coverage_gap",
        section="calendars",
        severity="warning",
        status="resolved",
        title="Resolved Alert",
        message="Already handled",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        resolved_at=datetime.now(UTC),
        resolved_by=user.id,
    )
    sess.add(resolved)

    sess.commit()
    sess.close()
    return {"open_ids": alert_ids}


@pytest.fixture
def client(session_local, user, seed_data):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/action-alerts
# ---------------------------------------------------------------------------


def test_list_action_alerts_defaults_to_open(client):
    resp = client.get("/api/action-alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    for item in data["items"]:
        assert item["status"] == "open"


def test_list_action_alerts_include_resolved(client):
    resp = client.get("/api/action-alerts?status=resolved")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_action_alerts_all_statuses(client):
    resp = client.get("/api/action-alerts?status=")
    assert resp.status_code == 200
    assert resp.json()["total"] == 4


def test_list_action_alerts_filter_by_severity(client):
    resp = client.get("/api/action-alerts?severity=critical")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["severity"] == "critical"


def test_list_action_alerts_no_match(client):
    resp = client.get("/api/action-alerts?severity=unknown")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/action-alerts/summary
# ---------------------------------------------------------------------------


def test_summary_action_alerts(client):
    resp = client.get("/api/action-alerts/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_open"] == 3
    assert "calendars" in data["by_section"]
    assert data["by_section"]["calendars"] == 3


# ---------------------------------------------------------------------------
# POST /api/action-alerts/{id}/resolve
# ---------------------------------------------------------------------------


def test_resolve_action_alert_success(client, seed_data):
    alert_id = seed_data["open_ids"][0]
    resp = client.post(f"/api/action-alerts/{alert_id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_resolve_action_alert_not_found(client):
    resp = client.post("/api/action-alerts/unknown-id/resolve")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/action-alerts/{id}/dismiss
# ---------------------------------------------------------------------------


def test_dismiss_action_alert_success(client, seed_data):
    alert_id = seed_data["open_ids"][0]
    resp = client.post(f"/api/action-alerts/{alert_id}/dismiss")
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_dismiss_action_alert_not_found(client):
    resp = client.post("/api/action-alerts/unknown-id/dismiss")
    assert resp.status_code == 404
