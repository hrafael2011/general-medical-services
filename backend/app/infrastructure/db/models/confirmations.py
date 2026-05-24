from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class ConfirmationRequestModel(Base):
    __tablename__ = "confirmation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    confirmation_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    response_token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False, index=True
    )
    notification_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notification_events.id"), nullable=True, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_assignments.id"), nullable=True, index=True
    )
    mission_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("mission_assignments.id"), nullable=True, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
