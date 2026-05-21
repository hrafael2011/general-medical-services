import logging
import os

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> None:
    """Send email via Resend. Falls back to console logging when no API key is configured."""
    if not settings.resend_api_key:
        logger.info("--- EMAIL (no API key configured) ---")
        logger.info("To: %s", to)
        logger.info("Subject: %s", subject)
        logger.info("Body: %s", html)
        logger.info("--- END EMAIL ---")
        return

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
