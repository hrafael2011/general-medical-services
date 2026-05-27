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


class MetaCloudAPIProvider:
    """WhatsApp provider using PyWa (Meta Cloud API)."""

    name = "meta_cloud_api"

    def __init__(self, phone_number_id: str | None = None) -> None:
        from backend.app.core.config import settings

        self.token = settings.meta_whatsapp_token
        self.phone_number_id = phone_number_id or settings.meta_whatsapp_phone_number_id
        self.api_version = settings.meta_whatsapp_api_version.lstrip("v")
        if not self.token or not self.phone_number_id:
            raise ValueError("Meta WhatsApp token y phone_number_id son requeridos")

    def send(self, phone: str, message: str) -> str:
        try:
            from backend.app.application.notifications.phone_utils import normalize_phone

            from pywa import WhatsApp

            client = WhatsApp(
                phone_id=self.phone_number_id,
                token=self.token,
                api_version=self.api_version,
            )
            clean_phone = normalize_phone(phone)
            msg = client.send_message(to=clean_phone, text=message)
            msg_id = msg.id if hasattr(msg, "id") else str(msg)
            logger.info("Meta message sent: %s to %s", msg_id, clean_phone)
            return msg_id
        except Exception as exc:
            error_code = getattr(exc, "code", None)
            logger.warning("Meta send failed (code=%s): %s", error_code, exc, exc_info=True)
            exc.error_code = error_code  # type: ignore[attr-defined]
            raise
