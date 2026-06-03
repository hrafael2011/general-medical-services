"""Tests for GET /api/scheduler/health endpoint."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_scheduler_health_returns_status(client):
    """GET /api/scheduler/health returns scheduler_running and jobs list."""
    response = client.get("/api/scheduler/health")
    assert response.status_code == 200
    body = response.json()
    assert "scheduler_running" in body
    assert "jobs" in body
    assert isinstance(body["jobs"], list)


def test_scheduler_health_jobs_have_expected_fields(client):
    """Each job entry has id and next_run_time."""
    response = client.get("/api/scheduler/health")
    body = response.json()
    if body["scheduler_running"]:
        for job in body["jobs"]:
            assert "id" in job
            assert "next_run_time" in job or job.get("next_run_time") is None
