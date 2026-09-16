import logging
import base64
from html import escape
from email.message import EmailMessage

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, html: str) -> bool:
    """Send email via Resend, Gmail API, or fall back to console logging.

    Priority:
    1. Resend — when RESEND_API_KEY is configured
    2. Gmail API — when Gmail OAuth credentials are configured
    3. Log — when no provider is configured

    Returns True only when a provider confirmed delivery. Callers must not assume the
    message went out: a misconfigured or rejected provider is reported as False rather
    than raised, so the caller's transaction still commits.
    """
    delivery = _prepare_delivery(to=to, subject=subject, html=html)
    if delivery is None:
        return False

    to = delivery["to"]
    subject = delivery["subject"]
    html = delivery["html"]

    if settings.resend_api_key:
        return _send_via_resend(to, subject, html)

    if (
        settings.gmail_client_id
        and settings.gmail_client_secret
        and settings.gmail_refresh_token
    ):
        return _send_via_gmail_api(to, subject, html)

    logger.info("--- EMAIL (no provider configured) ---")
    logger.info("To: %s", to)
    logger.info("Subject: %s", subject)
    logger.info("Body: %s", html)
    logger.info("--- END EMAIL ---")
    return False


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


def _send_via_resend(to: str, subject: str, html: str) -> bool:
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
        return True
    except Exception:
        logger.exception("Failed to send email via Resend")
        return False


def _send_via_gmail_api(to: str, subject: str, html: str) -> bool:
    from_email = settings.gmail_from_email
    if not from_email:
        logger.error("Gmail API email requested but no sender is configured")
        return False

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
            try:
                token_response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # raise_for_status() would otherwise discard the body, which is the part
                # that names the cause.
                _log_delivery_error("Gmail OAuth token refresh", exc.response)
                return False

            access_token = token_response.json()["access_token"]

            send_response = client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
            )
            try:
                send_response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                _log_delivery_error("Gmail message send", exc.response)
                return False
        logger.info("Email sent to %s via Gmail API", to)
        return True
    except Exception:
        logger.exception("Failed to send email via Gmail API")
        return False


def _log_delivery_error(context: str, response: httpx.Response) -> None:
    """Log why a provider refused the request, without echoing any credential.

    Google names the cause in the response body, and for OAuth that name is the whole
    diagnosis: `invalid_grant` means the refresh token expired or was revoked and the
    authorization has to be redone, while `invalid_client` means the client id/secret do
    not match. Only those fields are read, so an `access_token` in the payload can never
    reach the log.
    """
    status_code = getattr(response, "status_code", "unknown")
    reason = _extract_error_reason(response)
    if reason:
        logger.error("%s rejected: HTTP %s — %s", context, status_code, reason)
    else:
        logger.error("%s rejected: HTTP %s (no error detail in body)", context, status_code)


def _extract_error_reason(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    error = payload.get("error")

    # Google API style: {"error": {"code": 403, "message": "...", "status": "..."}}
    if isinstance(error, dict):
        message = error.get("message")
        status = error.get("status")
        if message and status:
            return f"{status}: {message}"
        return str(message) if message else None

    # OAuth style: {"error": "invalid_grant", "error_description": "..."}
    if isinstance(error, str):
        description = payload.get("error_description")
        return f"{error}: {description}" if description else error

    return None


def _build_email_message(*, from_email: str, to: str, subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to
    msg.set_content("Este correo requiere HTML. Por favor usa un cliente compatible.", subtype="plain")
    msg.add_alternative(html, subtype="html")
    return msg
