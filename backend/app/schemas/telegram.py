from datetime import datetime
from pydantic import BaseModel, Field


class TelegramUserLinkRead(BaseModel):
    id: str
    telegram_user_id: str
    telegram_username: str | None
    user_id: str
    active: bool
    linked_by: str | None
    linked_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class CreateTelegramLinkRequest(BaseModel):
    telegram_user_id: str = Field(min_length=1, max_length=60)
    telegram_username: str | None = Field(default=None, max_length=120)
    user_id: str


class TelegramInteractionRead(BaseModel):
    id: str
    telegram_user_id: str
    matched_user_id: str | None
    user_role: str | None
    intent_id: str | None
    input_text: str
    intent_confidence: float | None
    tool_name: str | None
    response_text: str | None
    fallback_reason: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TelegramWebhookUpdate(BaseModel):
    """Telegram Bot API update payload (subset needed for MVP)."""
    update_id: int
    message: "TelegramMessage | None" = None


class TelegramMessage(BaseModel):
    message_id: int
    text: str | None = None
    from_: "TelegramUser | None" = Field(default=None, alias="from")
    chat: "TelegramChat"

    model_config = {"populate_by_name": True}


class TelegramUser(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str


TelegramWebhookUpdate.model_rebuild()
TelegramMessage.model_rebuild()
