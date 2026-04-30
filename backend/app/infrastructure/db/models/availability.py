from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class DoctorAvailabilityModel(Base):
    __tablename__ = "doctor_availability"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False
    )
    availability_type: Mapped[str] = mapped_column(String(30), nullable=False)
    days_of_week: Mapped[list | None] = mapped_column(JSON, nullable=True)
    available_dates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approved"
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DoctorRestrictionModel(Base):
    __tablename__ = "doctor_restrictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False
    )
    reason_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deactivation_reasons.id"), nullable=True
    )
    restriction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    starts_at: Mapped[date] = mapped_column(Date, nullable=False)
    ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approved"
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lifted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
