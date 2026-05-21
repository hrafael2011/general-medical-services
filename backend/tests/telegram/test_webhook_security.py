from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from backend.app.api.routes.telegram import (
    _RATE_LIMIT_BUCKET,
    _build_rate_limited_tool_response,
    _get_linkable_user,
    _is_rate_limited,
)
from backend.tests.telegram.test_orchestrator import _new_user


def test_webhook_rate_limiter_allows_until_configured_limit() -> None:
    """Webhook limiter should allow messages up to the configured per-minute limit."""
    _RATE_LIMIT_BUCKET.clear()
    now = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)

    assert _is_rate_limited("tg-1", limit_per_minute=2, now=now) is False
    assert _is_rate_limited("tg-1", limit_per_minute=2, now=now) is False


def test_webhook_rate_limiter_blocks_and_tracks_excess_messages() -> None:
    """Excess messages should be rejected explicitly, not dropped silently."""
    _RATE_LIMIT_BUCKET.clear()
    now = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)

    _is_rate_limited("tg-1", limit_per_minute=1, now=now)

    assert _is_rate_limited("tg-1", limit_per_minute=1, now=now) is True


def test_webhook_rate_limiter_resets_after_window() -> None:
    """A new minute window should allow the same Telegram user again."""
    _RATE_LIMIT_BUCKET.clear()
    first = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    second = datetime(2026, 5, 16, 12, 1, tzinfo=UTC)

    _is_rate_limited("tg-1", limit_per_minute=1, now=first)

    assert _is_rate_limited("tg-1", limit_per_minute=1, now=second) is False


def test_rate_limited_interaction_has_observability_payload() -> None:
    """Discarded webhook messages should explain why they were discarded."""
    payload = _build_rate_limited_tool_response()

    assert payload["observability"]["action"] == "discarded"
    assert payload["observability"]["route"] == "webhook_rate_limit"
    assert payload["observability"]["fallback_reason"] == "rate_limited"
    assert payload["observability"]["has_document"] is False


def test_get_linkable_user_allows_admin_and_encargado(db_session) -> None:
    """Only internal roles can receive Telegram assistant links."""
    admin = _new_user(db_session, role="admin")
    encargado = _new_user(db_session, role="encargado")

    assert _get_linkable_user(db_session, admin.id).id == admin.id
    assert _get_linkable_user(db_session, encargado.id).id == encargado.id


def test_get_linkable_user_rejects_doctor_role(db_session) -> None:
    """Doctors are not linkable to the internal assistant."""
    doctor = _new_user(db_session, role="doctor")

    with pytest.raises(HTTPException) as exc:
        _get_linkable_user(db_session, doctor.id)

    assert exc.value.status_code == 400
