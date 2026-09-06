from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base

# NOTA (2026-09-06): ScheduledJobModel y JobExecutionModel fueron eliminados —
# el scheduler real es AsyncIOScheduler en memoria (main.py) y las tablas
# scheduled_jobs/job_executions quedaron huérfanas en la migración original.


class NotificationEventModel(Base):
    __tablename__ = "notification_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_doctor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True, index=True
    )
    recipient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_assignments.id"), nullable=True, index=True
    )
    mission_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("mission_assignments.id"), nullable=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_retried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
