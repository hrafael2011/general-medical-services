"""create missions

Revision ID: 20260429_0005
Revises: 20260429_0004
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0005"
down_revision: str | None = "20260429_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mission_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mission_date", sa.Date(), nullable=False),
        sa.Column("mission_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mission_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("participant_count", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("confirmed_by", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mission_participants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mission_assignment_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("selection_source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("ranking_position", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mission_assignment_id"], ["mission_assignments.id"], name="fk_mission_participants_mission_assignment"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], name="fk_mission_participants_doctor"),
    )
    op.create_index("ix_mission_participants_mission_assignment_id", "mission_participants", ["mission_assignment_id"])
    op.create_index("ix_mission_participants_doctor_id", "mission_participants", ["doctor_id"])

    op.create_table(
        "mission_candidate_rankings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("calendar_version_id", sa.String(length=36), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("month", "year", name="uq_mission_candidate_rankings_month_year"),
        sa.ForeignKeyConstraint(["calendar_version_id"], ["calendar_versions.id"], name="fk_mission_candidate_rankings_calendar_version"),
    )

    op.create_table(
        "mission_candidate_ranking_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mission_candidate_ranking_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("ranking_position", sa.Integer(), nullable=False),
        sa.Column("total_load_score", sa.Float(), nullable=False),
        sa.Column("monthly_service_load", sa.Float(), nullable=False),
        sa.Column("recent_service_load", sa.Float(), nullable=False),
        sa.Column("monthly_mission_load", sa.Float(), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["mission_candidate_ranking_id"], ["mission_candidate_rankings.id"], name="fk_mission_ranking_entries_ranking"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], name="fk_mission_ranking_entries_doctor"),
    )
    op.create_index("ix_mission_ranking_entries_ranking_id", "mission_candidate_ranking_entries", ["mission_candidate_ranking_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_ranking_entries_ranking_id", table_name="mission_candidate_ranking_entries")
    op.drop_table("mission_candidate_ranking_entries")
    op.drop_table("mission_candidate_rankings")
    op.drop_index("ix_mission_participants_doctor_id", table_name="mission_participants")
    op.drop_index("ix_mission_participants_mission_assignment_id", table_name="mission_participants")
    op.drop_table("mission_participants")
    op.drop_table("mission_assignments")
