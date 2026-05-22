"""Tests for health check endpoints."""

from unittest.mock import MagicMock, patch

from backend.app.api.routes.health import health_check
from backend.app.main import create_app


def test_health_check_returns_ok() -> None:
    response = health_check()

    assert response["status"] == "ok"


def test_app_registers_health_route() -> None:
    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/api/health" in route_paths


def test_health_ready_returns_ok_when_db_available() -> None:
    """health/ready returns ok when DB is reachable."""
    mock_session = MagicMock()
    with patch("backend.app.api.routes.health.SessionLocal", return_value=mock_session):
        from backend.app.api.routes.health import health_readiness

        result = health_readiness()

    assert result == {"status": "ok", "database": "connected"}
    mock_session.execute.assert_called_once()
    mock_session.close.assert_called_once()


def test_health_ready_returns_generic_error_when_db_unavailable() -> None:
    """health/ready does NOT leak DB internals on failure."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = Exception(
        "connection refused — postgres://user:secret@host:5432/db"
    )
    with patch("backend.app.api.routes.health.SessionLocal", return_value=mock_session):
        from backend.app.api.routes.health import health_readiness

        result = health_readiness()

    assert result == {"status": "error", "database": "unavailable"}
    mock_session.close.assert_called_once()
