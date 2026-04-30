from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.db.base import Base


class MissionAssignmentModel(Base):
    __tablename__ = "mission_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mission_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mission_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MissionParticipantModel(Base):
    __tablename__ = "mission_participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mission_assignments.id"), nullable=False, index=True
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False, index=True
    )
    selection_source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="manual"
    )
    ranking_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MissionCandidateRankingModel(Base):
    __tablename__ = "mission_candidate_rankings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_versions.id"), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (UniqueConstraint("month", "year"),)


class MissionCandidateRankingEntryModel(Base):
    __tablename__ = "mission_candidate_ranking_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mission_candidate_ranking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mission_candidate_rankings.id"), nullable=False, index=True
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False
    )
    ranking_position: Mapped[int] = mapped_column(Integer, nullable=False)
    total_load_score: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_service_load: Mapped[float] = mapped_column(Float, nullable=False)
    recent_service_load: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_mission_load: Mapped[float] = mapped_column(Float, nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
