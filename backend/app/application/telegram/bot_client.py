class TelegramBotClient:
    """Sends messages via Telegram Bot API."""

    def __init__(self) -> None:
        import os

        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, chat_id: int | str, text: str) -> bool:
        """Send a text message. Returns True on success, False on failure."""
        import httpx  # type: ignore[import]

        try:
            resp = httpx.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception:
            return False


class FakeBotClient:
    """In-memory fake for tests."""

    sent: list[dict]

    def __init__(self) -> None:
        self.sent = []

    def send_message(self, chat_id: int | str, text: str) -> bool:
        self.sent.append({"chat_id": chat_id, "text": text})
        return True
