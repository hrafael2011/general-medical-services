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
            error_msg = str(exc)
            if error_code == 131026 or "template" in error_msg.lower():
                logger.warning(
                    "Meta template required — message not sent. "
                    "Approve a template in Meta Business Manager or use a "
                    "pre-approved template. message=%s, error=%s",
                    message[:120],
                    error_msg,
                )
            else:
                logger.warning(
                    "Meta send failed (code=%s): %s", error_code, exc, exc_info=True
                )
            exc.error_code = error_code  # type: ignore[attr-defined]
            raise


class TelegramNotificationProvider:
    """Notification provider that sends messages via Telegram Bot API.

    The 'phone' parameter in send() is repurposed as the telegram
    chat_id. Triggers use _resolve_recipient_phone() which prefers
    telegram_chat_id, falling back to whatsapp_phone.
    """

    name = "telegram"

    def __init__(self) -> None:
        from backend.app.core.config import settings

        self.token = settings.telegram_notification_bot_token
        if not self.token:
            raise ValueError("telegram_notification_bot_token is required")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, phone: str, message: str) -> str:
        """Send a notification message via Telegram.

        Args:
            phone: The telegram chat_id (repurposed field name from
                   the NotificationProvider protocol).
            message: The message text to send (may include HTML).
        """
        import uuid as _uuid

        try:
            import httpx

            chat_id = phone
            resp = httpx.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(
                    f"Telegram API error: {data.get('description', 'unknown')}"
                )

            msg_id = str(data["result"]["message_id"])
            logger.info("Telegram message sent: %s to chat %s", msg_id, chat_id)
            return msg_id
        except Exception as exc:
            logger.warning(
                "Telegram send failed (chat=%s): %s", phone, exc, exc_info=True
            )
            raise
