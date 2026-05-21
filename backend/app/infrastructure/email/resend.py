import logging
import smtplib
import base64
from email.message import EmailMessage

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> None:
    """Send email via Resend, SMTP, or fall back to console logging.

    Priority:
    1. Resend — when RESEND_API_KEY is configured
    2. Gmail API — when Gmail OAuth credentials are configured
    3. SMTP — when SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are configured
    4. Log — when no provider is configured
    """
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

    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        _send_via_smtp(to, subject, html)
        return

    logger.info("--- EMAIL (no provider configured) ---")
    logger.info("To: %s", to)
    logger.info("Subject: %s", subject)
    logger.info("Body: %s", html)
    logger.info("--- END EMAIL ---")


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
    from_email = settings.gmail_from_email or settings.smtp_from_email or settings.smtp_username
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


def _send_via_smtp(to: str, subject: str, html: str) -> None:
    from_email = settings.smtp_from_email or settings.smtp_username
    msg = _build_email_message(from_email=from_email, to=to, subject=subject, html=html)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)  # type: ignore[arg-type]
            server.send_message(msg)
        logger.info("Email sent to %s via SMTP (%s)", to, settings.smtp_host)
    except Exception:
        logger.exception("Failed to send email via SMTP")


def _build_email_message(*, from_email: str, to: str, subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to
    msg.set_content("Este correo requiere HTML. Por favor usa un cliente compatible.", subtype="plain")
    msg.add_alternative(html, subtype="html")
    return msg
