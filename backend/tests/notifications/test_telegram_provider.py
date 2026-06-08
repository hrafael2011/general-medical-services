"""Tests for TelegramNotificationProvider — all use httpx mock."""

from unittest.mock import MagicMock, patch

import pytest


class TestTelegramNotificationProvider:
    """Tests for TelegramNotificationProvider.send()."""

    def _make_provider(self):
        """Create a provider instance without calling the real __init__."""
        from backend.app.application.notifications.providers import (
            TelegramNotificationProvider,
        )
        provider = TelegramNotificationProvider.__new__(TelegramNotificationProvider)
        provider.base_url = "https://api.telegram.org/bot/test"
        provider.token = "test"
        return provider

    def test_send_success_returns_message_id(self):
        """Successful send returns the Telegram message_id."""
        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"message_id": 12345},
        }

        with patch("httpx.post", return_value=mock_resp):
            msg_id = provider.send("123456789", "Test message")

        assert msg_id == "12345"

    def test_send_http_failure_raises(self):
        """HTTP failure raises exception."""
        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(Exception):
                provider.send("123456789", "Test")

    def test_send_api_error_raises_runtime_error(self):
        """Telegram API ok=False raises RuntimeError."""
        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }

        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Telegram API error"):
                provider.send("123456789", "Test")

    def test_provider_name_is_telegram(self):
        """Provider.name returns 'telegram'."""
        from backend.app.application.notifications.providers import (
            TelegramNotificationProvider,
        )
        assert TelegramNotificationProvider.name == "telegram"
