"""Add deleted_at to deactivation_reasons

Revision ID: 20260524_0036
Revises: 20260523_0035
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0036"
down_revision: str | None = "20260523_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE deactivation_reasons
        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE deactivation_reasons
        DROP COLUMN IF EXISTS deleted_at;
    """)
