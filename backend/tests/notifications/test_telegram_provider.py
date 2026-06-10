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

    def test_send_with_dict_message_includes_reply_markup(self):
        """When message is a dict with text and reply_markup, both are sent."""
        provider = self._make_provider()
        dict_msg = {
            "text": "Confirm your shift",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "✓ Confirmar asistencia", "callback_data": "confirm:abc123"}
                ]]
            },
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_resp
            msg_id = provider.send("123456789", dict_msg)

        assert msg_id == "42"
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["chat_id"] == "123456789"
        assert payload["text"] == "Confirm your shift"
        assert "reply_markup" in payload
        assert payload["reply_markup"] == dict_msg["reply_markup"]
        assert payload["parse_mode"] == "HTML"

    def test_send_with_string_message_still_works(self):
        """String messages should still work as before."""
        provider = self._make_provider()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 77}}

        with patch("httpx.post") as mock_post:
            mock_post.return_value = mock_resp
            msg_id = provider.send("123456789", "Plain text")

        assert msg_id == "77"
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["text"] == "Plain text"
        assert "reply_markup" not in payload
