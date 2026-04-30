from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class TelegramUserLinkModel(Base):
    __tablename__ = "telegram_user_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    telegram_user_id: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    linked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelegramInteractionModel(Base):
    __tablename__ = "telegram_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    telegram_user_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    matched_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    intent_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tool_request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
