from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)
