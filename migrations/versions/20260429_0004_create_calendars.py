"""create calendars

Revision ID: 20260429_0004
Revises: 20260429_0003
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0004"
down_revision: str | None = "20260429_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendars",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("year", "month", name="uq_calendars_year_month"),
    )
    op.create_index("ix_calendars_status", "calendars", ["status"])
    op.create_index("ix_calendars_year_month", "calendars", ["year", "month"])

    op.create_table(
        "calendar_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("calendar_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_id"], ["calendars.id"], name="fk_calendar_versions_calendar_id_calendars"),
    )
    op.create_index("ix_calendar_versions_calendar_id", "calendar_versions", ["calendar_id"])

    op.create_table(
        "calendar_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("calendar_version_id", sa.String(length=36), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("service_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_area_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("assignment_source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("rationale", sa.JSON(), nullable=True),
        sa.Column("override_justification", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_version_id"], ["calendar_versions.id"], name="fk_calendar_assignments_calendar_version_id_calendar_versions"),
        sa.ForeignKeyConstraint(["service_area_id"], ["service_areas.id"], name="fk_calendar_assignments_service_area_id_service_areas"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], name="fk_calendar_assignments_doctor_id_doctors"),
    )
    op.create_index("ix_calendar_assignments_version_id", "calendar_assignments", ["calendar_version_id"])
    op.create_index("ix_calendar_assignments_service_date", "calendar_assignments", ["service_date"])
    op.create_index("ix_calendar_assignments_doctor_id", "calendar_assignments", ["doctor_id"])

    op.create_table(
        "unresolved_gaps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("calendar_version_id", sa.String(length=36), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("service_area_id", sa.String(length=36), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["calendar_version_id"], ["calendar_versions.id"], name="fk_unresolved_gaps_calendar_version_id_calendar_versions"),
        sa.ForeignKeyConstraint(["service_area_id"], ["service_areas.id"], name="fk_unresolved_gaps_service_area_id_service_areas"),
    )
    op.create_index("ix_unresolved_gaps_version_id", "unresolved_gaps", ["calendar_version_id"])


def downgrade() -> None:
    op.drop_index("ix_unresolved_gaps_version_id", table_name="unresolved_gaps")
    op.drop_table("unresolved_gaps")
    op.drop_index("ix_calendar_assignments_doctor_id", table_name="calendar_assignments")
    op.drop_index("ix_calendar_assignments_service_date", table_name="calendar_assignments")
    op.drop_index("ix_calendar_assignments_version_id", table_name="calendar_assignments")
    op.drop_table("calendar_assignments")
    op.drop_index("ix_calendar_versions_calendar_id", table_name="calendar_versions")
    op.drop_table("calendar_versions")
    op.drop_index("ix_calendars_year_month", table_name="calendars")
    op.drop_index("ix_calendars_status", table_name="calendars")
    op.drop_table("calendars")
