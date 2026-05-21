"""Telegram conversation session persistence model."""

from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class TelegramSessionModel(Base):
    __tablename__ = "telegram_sessions"

    telegram_user_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    session_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
