class TelegramBotClient:
    """Sends messages and documents via Telegram Bot API."""

    def __init__(self) -> None:
        from backend.app.core.config import settings

        self.token = settings.telegram_bot_token or ""
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

    def send_document(
        self, chat_id: int | str, file_bytes: bytes, filename: str
    ) -> bool:
        """Send a file as a document. Returns True on success, False on failure."""
        import httpx  # type: ignore[import]

        try:
            resp = httpx.post(
                f"{self.base_url}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": (filename, file_bytes)},
                timeout=30.0,
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

    def send_document(
        self, chat_id: int | str, file_bytes: bytes, filename: str
    ) -> bool:
        self.sent.append({"chat_id": chat_id, "document": filename, "size": len(file_bytes)})
        return True
