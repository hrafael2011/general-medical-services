"""Tests for Telegram webhook secret token validation (X-Telegram-Bot-Api-Secret-Token).

Verifies that:
1. When FEATURE_TELEGRAM=False, the webhook endpoint returns 404
2. When TELEGRAM_WEBHOOK_SECRET is set, missing/wrong header returns 403
3. When TELEGRAM_WEBHOOK_SECRET is set, correct header passes through
4. When TELEGRAM_WEBHOOK_SECRET is not set, requests work without the header (backward compat)
"""

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.api.routes.telegram import (
    get_orchestrator,
    router as telegram_router,
)
from backend.app.core.config import settings
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# Test app with telegram routes included and deps overridden
# ---------------------------------------------------------------------------

_test_app = FastAPI()
_test_app.include_router(telegram_router)
# These dependency overrides return None — the webhook function will
# early-return before using them when the payload has no message field.
_test_app.dependency_overrides[get_db_session] = lambda: None
_test_app.dependency_overrides[get_orchestrator] = lambda: None
_test_client = TestClient(_test_app)

MINIMAL_PAYLOAD = {"update_id": 1}


@contextmanager
def _with_telegram_config(*, feature_enabled: bool = True, webhook_secret: str | None = None):
    """Temporarily override telegram-related settings for a test."""
    original_feature = settings.feature_telegram
    original_secret = settings.telegram_webhook_secret
    settings.feature_telegram = feature_enabled
    settings.telegram_webhook_secret = webhook_secret
    try:
        yield
    finally:
        settings.feature_telegram = original_feature
        settings.telegram_webhook_secret = original_secret


# --- Disabled feature test ---------------------------------------------------

class TestTelegramFeatureDisabled:
    """When FEATURE_TELEGRAM=False, the webhook endpoint must return 404."""

    def test_webhook_returns_404_when_feature_disabled(self) -> None:
        """POST /api/telegram/webhook returns 404 when Telegram is disabled."""
        app = create_app()
        client = TestClient(app)
        response = client.post("/api/telegram/webhook", json=MINIMAL_PAYLOAD)
        assert response.status_code == 404


# --- Secret validation tests -------------------------------------------------

class TestWebhookSecretValidation:
    """X-Telegram-Bot-Api-Secret-Token header validation on the webhook."""

    def test_rejects_missing_secret(self) -> None:
        """When secret is configured, missing header must return 403."""
        with _with_telegram_config(feature_enabled=True, webhook_secret="s3cret!"):
            response = _test_client.post("/telegram/webhook", json=MINIMAL_PAYLOAD)
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

    def test_rejects_wrong_secret(self) -> None:
        """When secret is configured, wrong header value must return 403."""
        with _with_telegram_config(feature_enabled=True, webhook_secret="s3cret!"):
            response = _test_client.post(
                "/telegram/webhook",
                json=MINIMAL_PAYLOAD,
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            )
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}

    def test_accepts_correct_secret(self) -> None:
        """When secret is configured, correct header must pass through."""
        with _with_telegram_config(feature_enabled=True, webhook_secret="s3cret!"):
            response = _test_client.post(
                "/telegram/webhook",
                json=MINIMAL_PAYLOAD,
                headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret!"},
            )
        # Must not be 403 — validation passed
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_backward_compat_when_secret_not_configured(self) -> None:
        """No secret configured -> requests without header work (backward compat)."""
        with _with_telegram_config(feature_enabled=True, webhook_secret=None):
            response = _test_client.post(
                "/telegram/webhook",
                json=MINIMAL_PAYLOAD,
            )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
