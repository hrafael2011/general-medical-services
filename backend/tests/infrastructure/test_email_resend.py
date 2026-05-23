"""Tests for email sending — Resend, Gmail API, and logging fallback."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from backend.app.infrastructure.email.resend import send_email


@patch("backend.app.infrastructure.email.resend.settings")
def test_send_via_resend_when_api_key_set(mock_settings):
    """Sends via Resend when RESEND_API_KEY is configured."""
    mock_settings.email_mode = "send"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = ""
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"
    mock_settings.gmail_client_id = None
    mock_settings.gmail_client_secret = None
    mock_settings.gmail_refresh_token = None

    with patch(
        "backend.app.infrastructure.email.resend._send_via_resend"
    ) as mock_resend:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_resend.assert_called_once_with("a@b.com", "Test", "<p>hi</p>")


@patch("backend.app.infrastructure.email.resend.settings")
def test_fallback_to_log_when_no_provider(mock_settings):
    """Logs to console when no provider is configured."""
    mock_settings.email_mode = "send"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = ""
    mock_settings.resend_api_key = None
    mock_settings.gmail_client_id = None
    mock_settings.gmail_client_secret = None
    mock_settings.gmail_refresh_token = None

    with patch("backend.app.infrastructure.email.resend.logger") as mock_logger:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_logger.info.assert_any_call("--- EMAIL (no provider configured) ---")


@patch("backend.app.infrastructure.email.resend.settings")
def test_gmail_chosen_over_log_when_configured(mock_settings):
    """Uses Gmail API before falling back to log when Resend is not configured."""
    mock_settings.email_mode = "send"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = ""
    mock_settings.resend_api_key = None
    mock_settings.gmail_client_id = "gmail-client"
    mock_settings.gmail_client_secret = "gmail-secret"
    mock_settings.gmail_refresh_token = "gmail-refresh"
    mock_settings.gmail_from_email = "Sistema <user@gmail.com>"

    with patch(
        "backend.app.infrastructure.email.resend._send_via_gmail_api"
    ) as mock_gmail, patch(
        "backend.app.infrastructure.email.resend.logger"
    ) as mock_logger:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_gmail.assert_called_once()
        mock_logger.info.assert_not_called()


@patch("backend.app.infrastructure.email.resend.settings")
def test_resend_takes_priority_over_gmail(mock_settings):
    """Uses Resend when both Resend and Gmail API are configured."""
    mock_settings.email_mode = "send"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = ""
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"
    mock_settings.gmail_client_id = "gmail-client"
    mock_settings.gmail_client_secret = "gmail-secret"
    mock_settings.gmail_refresh_token = "gmail-refresh"
    mock_settings.gmail_from_email = "Sistema <user@gmail.com>"

    with patch(
        "backend.app.infrastructure.email.resend._send_via_resend"
    ) as mock_resend, patch(
        "backend.app.infrastructure.email.resend._send_via_gmail_api"
    ) as mock_gmail:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_resend.assert_called_once()
        mock_gmail.assert_not_called()


@patch("backend.app.infrastructure.email.resend.settings")
def test_send_via_gmail_api_when_resend_missing_and_gmail_configured(mock_settings):
    """Uses Gmail API when Resend is not configured but Gmail OAuth credentials are."""
    mock_settings.email_mode = "send"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = ""
    mock_settings.resend_api_key = None
    mock_settings.gmail_client_id = "gmail-client"
    mock_settings.gmail_client_secret = "gmail-secret"
    mock_settings.gmail_refresh_token = "gmail-refresh"
    mock_settings.gmail_from_email = "Sistema <user@gmail.com>"

    with patch(
        "backend.app.infrastructure.email.resend._send_via_gmail_api"
    ) as mock_gmail:
        send_email(to="a@b.com", subject="Test", html="<p>hi</p>")
        mock_gmail.assert_called_once_with("a@b.com", "Test", "<p>hi</p>")


@patch("backend.app.infrastructure.email.resend.settings")
def test_redirect_mode_sends_to_safe_inbox_with_original_recipient(mock_settings):
    mock_settings.email_mode = "redirect"
    mock_settings.email_redirect_to = "hendrickrafaelbackup@gmail.com"
    mock_settings.email_subject_prefix = "[STAGING]"
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.resend_from_email = "noreply@test.com"
    mock_settings.gmail_client_id = None
    mock_settings.gmail_client_secret = None
    mock_settings.gmail_refresh_token = None

    with patch("backend.app.infrastructure.email.resend._send_via_resend") as mock_resend:
        send_email(to="real-user@example.com", subject="Invitacion", html="<p>link</p>")

    redirected_html = mock_resend.call_args.args[2]
    mock_resend.assert_called_once()
    assert mock_resend.call_args.args[0] == "hendrickrafaelbackup@gmail.com"
    assert mock_resend.call_args.args[1] == "[STAGING] Invitacion"
    assert "real-user@example.com" in redirected_html
    assert "<p>link</p>" in redirected_html


@patch("backend.app.infrastructure.email.resend.settings")
def test_redirect_mode_without_redirect_address_logs_instead_of_sending(mock_settings):
    mock_settings.email_mode = "redirect"
    mock_settings.email_redirect_to = None
    mock_settings.email_subject_prefix = "[STAGING]"
    mock_settings.resend_api_key = "re_abc123"
    mock_settings.gmail_client_id = None
    mock_settings.gmail_client_secret = None
    mock_settings.gmail_refresh_token = None

    with patch("backend.app.infrastructure.email.resend._send_via_resend") as mock_resend, patch(
        "backend.app.infrastructure.email.resend.logger"
    ) as mock_logger:
        send_email(to="real-user@example.com", subject="Invitacion", html="<p>link</p>")

    mock_resend.assert_not_called()
    mock_logger.error.assert_called_once_with(
        "EMAIL_MODE=redirect configured but EMAIL_REDIRECT_TO is empty"
    )


@patch("backend.app.infrastructure.email.resend.settings")
def test_gmail_api_sender_refreshes_token_and_posts_raw_message(mock_settings):
    """_send_via_gmail_api refreshes OAuth token and sends a base64url MIME message."""
    mock_settings.gmail_client_id = "gmail-client"
    mock_settings.gmail_client_secret = "gmail-secret"
    mock_settings.gmail_refresh_token = "gmail-refresh"
    mock_settings.gmail_from_email = "Sistema <user@gmail.com>"

    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "access-token"}
    send_response = MagicMock()

    def fake_post(url, **kwargs):
        if url == "https://oauth2.googleapis.com/token":
            return token_response
        if url == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send":
            return send_response
        raise AssertionError(f"Unexpected URL {url}")

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.side_effect = fake_post

    with patch("httpx.Client", return_value=mock_client):
        from backend.app.infrastructure.email.resend import _send_via_gmail_api

        _send_via_gmail_api("a@b.com", "Subject", "<p>body</p>")

    token_response.raise_for_status.assert_called_once()
    send_response.raise_for_status.assert_called_once()
    token_call = mock_client.post.call_args_list[0]
    assert token_call.kwargs["data"] == {
        "client_id": "gmail-client",
        "client_secret": "gmail-secret",
        "refresh_token": "gmail-refresh",
        "grant_type": "refresh_token",
    }
    send_call = mock_client.post.call_args_list[1]
    assert send_call.kwargs["headers"] == {"Authorization": "Bearer access-token"}
    raw = send_call.kwargs["json"]["raw"]
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    assert "From: Sistema <user@gmail.com>" in decoded
    assert "To: a@b.com" in decoded
    assert "Subject: Subject" in decoded
    assert "<p>body</p>" in decoded


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
