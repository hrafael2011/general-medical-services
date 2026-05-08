import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class NotificationProvider(Protocol):
    """Send a WhatsApp message. Returns provider message ID or raises."""

    def send(self, phone: str, message: str) -> str: ...

    @property
    def name(self) -> str: ...


class FakeProvider:
    """In-memory fake provider for tests and development."""

    name = "fake"
    sent: list[dict]  # class-level list for inspection in tests

    def __init__(self) -> None:
        self.sent = []

    def send(self, phone: str, message: str) -> str:
        import uuid

        msg_id = f"fake-{uuid.uuid4().hex[:8]}"
        logger.info("FakeProvider sent to %s: %s", phone, msg_id)
        self.sent.append({"phone": phone, "message": message, "id": msg_id})
        return msg_id


class TwilioProvider:
    """Twilio WhatsApp provider. Reads credentials from environment."""

    name = "twilio"

    def __init__(self) -> None:
        from backend.app.core.config import settings

        self.account_sid = settings.twilio_account_sid or ""
        self.auth_token = settings.twilio_auth_token or ""
        self.from_number = settings.twilio_whatsapp_from

    def send(self, phone: str, message: str) -> str:
        try:
            from twilio.rest import Client  # type: ignore[import]

            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(
                from_=self.from_number,
                to=f"whatsapp:{phone}",
                body=message,
            )
            logger.info("Twilio message sent: %s to %s", msg.sid, phone)
            return msg.sid
        except Exception as exc:
            error_code = None
            # Try to extract Twilio-specific error code
            if hasattr(exc, "code"):
                error_code = str(exc.code)
            elif hasattr(exc, "status"):
                error_code = str(exc.status)

            logger.warning(
                "Twilio send failed (code=%s): %s", error_code, exc,
                exc_info=True,
            )

            # Re-raise with error_code attached for the caller to store
            exc.error_code = error_code  # type: ignore[attr-defined]
            raise
