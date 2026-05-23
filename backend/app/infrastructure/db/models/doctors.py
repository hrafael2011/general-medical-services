from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class DoctorModel(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(160), nullable=False, unique=True, index=True
    )
    sex: Mapped[str] = mapped_column(String(10), nullable=False)
    rank_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ranks.id"), nullable=True, index=True
    )
    department_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("departments.id"), nullable=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    service_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    service_inactive_reason_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deactivation_reasons.id"), nullable=True, index=True
    )
    service_inactive_detail: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    participa_misiones: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    whatsapp_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    monthly_service_target: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )
    monthly_service_max: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    monthly_service_limit_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warn_only"
    )
    availability_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deactivated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class DoctorAllowedAreaModel(Base):
    __tablename__ = "doctor_allowed_areas"

    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), primary_key=True
    )
    service_area_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("service_areas.id"), primary_key=True
    )
