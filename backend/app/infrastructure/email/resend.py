import logging
import smtplib
from email.message import EmailMessage

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> None:
    """Send email via Resend, SMTP, or fall back to console logging.

    Priority:
    1. Resend — when RESEND_API_KEY is configured
    2. SMTP — when SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD are configured
    3. Log — when no provider is configured
    """
    if settings.resend_api_key:
        _send_via_resend(to, subject, html)
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


def _send_via_smtp(to: str, subject: str, html: str) -> None:
    from_email = settings.smtp_from_email or settings.smtp_username

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to
    msg.set_content("Este correo requiere HTML. Por favor usa un cliente compatible.", subtype="plain")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)  # type: ignore[arg-type]
            server.send_message(msg)
        logger.info("Email sent to %s via SMTP (%s)", to, settings.smtp_host)
    except Exception:
        logger.exception("Failed to send email via SMTP")
