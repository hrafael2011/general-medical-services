"""Add generation mode to calendars

Revision ID: 20260512_0018
Revises: 20260507_0017
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260512_0018"
down_revision: str | None = "20260507_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calendars",
        sa.Column(
            "generation_mode",
            sa.String(length=30),
            nullable=False,
            server_default="manual",
        ),
    )
    op.alter_column("calendars", "generation_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("calendars", "generation_mode")
