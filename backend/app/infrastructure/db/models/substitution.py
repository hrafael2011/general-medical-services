"""SubstitutionRecord model for last-minute substitution changes."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class SubstitutionRecordModel(Base):
    __tablename__ = "substitution_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calendar_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_versions.id"), nullable=False, index=True
    )
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_area_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("service_areas.id"), nullable=False
    )
    original_doctor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True
    )
    substitute_doctor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="normal"
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
