"""Tests for security hardening configuration.

Ensures that /docs, /redoc, /openapi.json are disabled in production
and that CORS is locked down to only the Vercel frontend in production.
"""
from contextlib import contextmanager

import pytest
from starlette.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import create_app


@contextmanager
def _with_env(app_env: str):
    """Temporarily override settings.app_env so each test can isolate its env."""
    original = settings.app_env
    settings.app_env = app_env
    try:
        yield
    finally:
        settings.app_env = original


class TestDocsDisabledInProduction:
    """/docs, /redoc, /openapi.json must be disabled when APP_ENV=production."""

    def test_docs_accessible_in_development(self):
        with _with_env("local"):
            client = TestClient(create_app())
            response = client.get("/docs")
        assert response.status_code == 200

    def test_docs_returns_404_in_production(self):
        with _with_env("production"):
            client = TestClient(create_app())
            response = client.get("/docs")
        assert response.status_code == 404

    def test_openapi_accessible_in_development(self):
        with _with_env("local"):
            client = TestClient(create_app())
            response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_returns_404_in_production(self):
        with _with_env("production"):
            client = TestClient(create_app())
            response = client.get("/openapi.json")
        assert response.status_code == 404

    def test_redoc_accessible_in_development(self):
        with _with_env("local"):
            client = TestClient(create_app())
            response = client.get("/redoc")
        assert response.status_code == 200

    def test_redoc_returns_404_in_production(self):
        with _with_env("production"):
            client = TestClient(create_app())
            response = client.get("/redoc")
        assert response.status_code == 404


class TestCORSLockedInProduction:
    """CORS must be strict in production and permissive in non-production."""

    PRODUCTION_ORIGIN = "https://general-medical-services.vercel.app"
    EXTERNAL_ORIGIN = "https://evil-site.com"

    def test_production_allows_vercel_origin(self):
        with _with_env("production"):
            client = TestClient(create_app())
            response = client.get("/api/health", headers={"Origin": self.PRODUCTION_ORIGIN})
        assert response.headers.get("access-control-allow-origin") == self.PRODUCTION_ORIGIN

    def test_production_rejects_external_origin(self):
        with _with_env("production"):
            client = TestClient(create_app())
            response = client.get("/api/health", headers={"Origin": self.EXTERNAL_ORIGIN})
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin is None or allow_origin != self.EXTERNAL_ORIGIN

    @pytest.mark.parametrize("origin", [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8999",
        "http://127.0.0.1:5173",
    ])
    def test_non_production_allows_localhost(self, origin):
        with _with_env("local"):
            client = TestClient(create_app())
            response = client.get("/api/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin
