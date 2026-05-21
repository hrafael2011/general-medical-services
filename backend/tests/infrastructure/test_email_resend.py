"""Tests for email sending — Resend, SMTP fallback, and console logging fallback."""

from unittest.mock import MagicMock, patch

import pytest
from backend.app.infrastructure.email.resend import send_email


@patch("backend.app.infrastructure.email.resend.settings")
def test_send_via_resend_when_api_key_set(mock_settings):
    """Sends via Resend when RESEND_API_KEY is configured."""
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"
    mock_settings.smtp_host = None
    mock_settings.smtp_username = None
    mock_settings.smtp_password = None

    with patch(
        "backend.app.infrastructure.email.resend._send_via_resend"
    ) as mock_resend:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_resend.assert_called_once_with("a@b.com", "Test", "<p>hi</p>")


@patch("backend.app.infrastructure.email.resend.settings")
def test_send_via_smtp_when_resend_missing_and_smtp_configured(mock_settings):
    """Sends via SMTP when Resend is not configured but SMTP is."""
    mock_settings.resend_api_key = None
    mock_settings.smtp_host = "smtp.gmail.com"
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = "user@gmail.com"
    mock_settings.smtp_password = "app-pwd"
    mock_settings.smtp_from_email = None

    with patch(
        "backend.app.infrastructure.email.resend._send_via_smtp"
    ) as mock_smtp:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_smtp.assert_called_once_with("a@b.com", "Test", "<p>hi</p>")


@patch("backend.app.infrastructure.email.resend.settings")
def test_fallback_to_log_when_no_provider(mock_settings):
    """Logs to console when no provider is configured."""
    mock_settings.resend_api_key = None
    mock_settings.smtp_host = None
    mock_settings.smtp_username = None
    mock_settings.smtp_password = None

    with patch("backend.app.infrastructure.email.resend.logger") as mock_logger:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_logger.info.assert_any_call("--- EMAIL (no provider configured) ---")


@patch("backend.app.infrastructure.email.resend.settings")
def test_resend_takes_priority_over_smtp(mock_settings):
    """Uses Resend when both Resend and SMTP are configured."""
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"
    mock_settings.smtp_host = "smtp.gmail.com"
    mock_settings.smtp_username = "user@gmail.com"
    mock_settings.smtp_password = "app-pwd"
    mock_settings.smtp_from_email = None

    with patch(
        "backend.app.infrastructure.email.resend._send_via_resend"
    ) as mock_resend, patch(
        "backend.app.infrastructure.email.resend._send_via_smtp"
    ) as mock_smtp:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_resend.assert_called_once()
        mock_smtp.assert_not_called()


@patch("backend.app.infrastructure.email.resend.settings")
def test_smtp_sender_calls_smtplib(mock_settings):
    """_send_via_smtp connects to SMTP server and sends message."""
    mock_settings.smtp_host = "smtp.gmail.com"
    mock_settings.smtp_port = 587
    mock_settings.smtp_username = "user@gmail.com"
    mock_settings.smtp_password = "app-pwd"
    mock_settings.smtp_from_email = None

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_context
    mock_smtp_constructor = MagicMock(return_value=mock_context)
    with patch("smtplib.SMTP", mock_smtp_constructor):
        from backend.app.infrastructure.email.resend import _send_via_smtp

        _send_via_smtp("a@b.com", "Subject", "<p>body</p>")

        mock_smtp_constructor.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        mock_context.starttls.assert_called_once()
        mock_context.login.assert_called_once_with("user@gmail.com", "app-pwd")
        mock_context.send_message.assert_called_once()
        msg = mock_context.send_message.call_args[0][0]
        assert msg["To"] == "a@b.com"
        assert msg["Subject"] == "Subject"


@patch("backend.app.infrastructure.email.resend.settings")
def test_resend_sender_uses_resend_lib(mock_settings):
    """_send_via_resend calls resend.Emails.send with correct params."""
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"

    with patch("resend.Emails.send") as mock_resend_send:
        from backend.app.infrastructure.email.resend import _send_via_resend

        _send_via_resend("a@b.com", "Subject", "<p>body</p>")

        mock_resend_send.assert_called_once_with({
            "from": "noreply@test.com",
            "to": ["a@b.com"],
            "subject": "Subject",
            "html": "<p>body</p>",
        })
