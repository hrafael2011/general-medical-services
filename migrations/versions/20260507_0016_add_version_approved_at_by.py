"""Add approved_at/approved_by to calendar_versions

Revision ID: 20260507_0016
Revises: 20260507_0015
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0016"
down_revision: str | None = "20260507_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calendar_versions",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calendar_versions",
        sa.Column("approved_by", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calendar_versions", "approved_by")
    op.drop_column("calendar_versions", "approved_at")
