from typing import Protocol


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
        self.sent.append({"phone": phone, "message": message, "id": msg_id})
        return msg_id


class TwilioProvider:
    """Twilio WhatsApp provider. Reads credentials from environment."""

    name = "twilio"

    def __init__(self) -> None:
        import os

        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    def send(self, phone: str, message: str) -> str:
        try:
            from twilio.rest import Client  # type: ignore[import]

            client = Client(self.account_sid, self.auth_token)
            msg = client.messages.create(
                from_=self.from_number,
                to=f"whatsapp:{phone}",
                body=message,
            )
            return msg.sid
        except Exception as exc:
            raise Exception(str(exc)) from exc
