import logging
import base64
from html import escape
from email.message import EmailMessage

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> None:
    """Send email via Resend, Gmail API, or fall back to console logging.

    Priority:
    1. Resend — when RESEND_API_KEY is configured
    2. Gmail API — when Gmail OAuth credentials are configured
    3. Log — when no provider is configured
    """
    delivery = _prepare_delivery(to=to, subject=subject, html=html)
    if delivery is None:
        return

    to = delivery["to"]
    subject = delivery["subject"]
    html = delivery["html"]

    if settings.resend_api_key:
        _send_via_resend(to, subject, html)
        return

    if (
        settings.gmail_client_id
        and settings.gmail_client_secret
        and settings.gmail_refresh_token
    ):
        _send_via_gmail_api(to, subject, html)
        return

    logger.info("--- EMAIL (no provider configured) ---")
    logger.info("To: %s", to)
    logger.info("Subject: %s", subject)
    logger.info("Body: %s", html)
    logger.info("--- END EMAIL ---")


def _prepare_delivery(*, to: str, subject: str, html: str) -> dict[str, str] | None:
    if settings.email_mode != "redirect":
        return {"to": to, "subject": subject, "html": html}

    if not settings.email_redirect_to:
        logger.error("EMAIL_MODE=redirect configured but EMAIL_REDIRECT_TO is empty")
        return None

    prefix = settings.email_subject_prefix.strip()
    redirected_subject = f"{prefix} {subject}".strip() if prefix else subject
    redirected_html = (
        "<div style=\"border:1px solid #d1d5db;padding:12px;margin-bottom:16px\">"
        "<strong>Staging email redirect</strong><br>"
        f"Original recipient: {escape(to)}"
        "</div>"
        f"{html}"
    )
    return {
        "to": settings.email_redirect_to,
        "subject": redirected_subject,
        "html": redirected_html,
    }


def _send_via_resend(to: str, subject: str, html: str) -> None:
    try:
        import resend

        resend.api_key = settings.resend_api_key
        params = {
            "from": settings.resend_from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        resend.Emails.send(params)
        logger.info("Email sent to %s via Resend", to)
    except Exception:
        logger.exception("Failed to send email via Resend")


def _send_via_gmail_api(to: str, subject: str, html: str) -> None:
    from_email = settings.gmail_from_email
    if not from_email:
        logger.error("Gmail API email requested but no sender is configured")
        return

    msg = _build_email_message(from_email=from_email, to=to, subject=subject, html=html)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")

    try:
        with httpx.Client(timeout=30) as client:
            token_response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "refresh_token": settings.gmail_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            send_response = client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
            )
            send_response.raise_for_status()
        logger.info("Email sent to %s via Gmail API", to)
    except Exception:
        logger.exception("Failed to send email via Gmail API")


def _build_email_message(*, from_email: str, to: str, subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to
    msg.set_content("Este correo requiere HTML. Por favor usa un cliente compatible.", subtype="plain")
    msg.add_alternative(html, subtype="html")
    return msg
