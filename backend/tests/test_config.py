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


EXPECTED_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'"
)


class TestSecurityHeaders:
    """All responses must carry 4 security headers with correct values."""

    def test_health_endpoint_returns_security_headers(self):
        client = TestClient(create_app())
        response = client.get("/api/health")
        assert response.headers.get("Content-Security-Policy") == EXPECTED_CSP
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_api_endpoint_returns_security_headers(self):
        client = TestClient(create_app())
        response = client.get("/api/health/ready")
        assert response.headers.get("Content-Security-Policy") == EXPECTED_CSP
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_cors_preflight_returns_security_headers(self):
        client = TestClient(create_app())
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Content-Security-Policy") == EXPECTED_CSP
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"
from backend.app.core.config import get_settings


def test_environment_variables_override_dotenv_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=local",
                "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts",
                "SECRET_KEY=local-secret",
            ]
        )
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:secret@postgres.railway.internal:5432/railway")
    monkeypatch.setenv("SECRET_KEY", "production-secret")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_env == "production"
    assert settings.database_url == "postgresql+psycopg://postgres:secret@postgres.railway.internal:5432/railway"
    assert settings.secret_key == "production-secret"

    get_settings.cache_clear()
