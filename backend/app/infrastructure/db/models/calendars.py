from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class CalendarModel(Base):
    __tablename__ = "calendars"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    generation_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)


class CalendarVersionModel(Base):
    __tablename__ = "calendar_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class CalendarWeekModel(Base):
    __tablename__ = "calendar_weeks"

    __table_args__ = (
        UniqueConstraint(
            "calendar_version_id", "week_number",
            name="uq_calendar_weeks_version_week",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendars.id"), nullable=False, index=True
    )
    calendar_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_versions.id"), nullable=False, index=True
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    previous_assignments_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CalendarAssignmentModel(Base):
    __tablename__ = "calendar_assignments"

    __table_args__ = (
        UniqueConstraint(
            "calendar_version_id", "service_date", "service_area_id",
            name="uq_calendar_assignments_version_date_area",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calendar_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_versions.id"), nullable=False, index=True
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    service_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    service_area_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("service_areas.id"), nullable=False, index=True
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False, index=True
    )
    calendar_week_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_weeks.id"), nullable=True, index=True,
    )
    assignment_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
    rationale: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    override_justification: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UnresolvedGapModel(Base):
    __tablename__ = "unresolved_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    calendar_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_versions.id"), nullable=False, index=True
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_area_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("service_areas.id"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
