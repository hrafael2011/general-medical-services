"""Add last_retried_at column to notification_events

Revision ID: 20260507_0012
Revises: 20260507_0011
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0012"
down_revision: str | None = "20260507_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_events",
        sa.Column("last_retried_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_events", "last_retried_at")
