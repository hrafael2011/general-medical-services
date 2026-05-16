"""Create calendar_weeks table

Revision ID: 20260516_0019
Revises: 20260512_0018
Create Date: 2026-05-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260516_0019"
down_revision: str | None = "20260512_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_weeks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("calendar_id", sa.String(36), sa.ForeignKey("calendars.id"), nullable=False, index=True),
        sa.Column("calendar_version_id", sa.String(36), sa.ForeignKey("calendar_versions.id"), nullable=False, index=True),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("calendar_version_id", "week_number", name="uq_calendar_weeks_version_week"),
    )


def downgrade() -> None:
    op.drop_table("calendar_weeks")
