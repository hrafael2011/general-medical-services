"""Add deleted_at to calendar_versions

Revision ID: 20260528_0042
Revises: 20260527_0041
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260528_0042"
down_revision: str | None = "20260527_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'calendar_versions' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE calendar_versions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE calendar_versions DROP COLUMN IF EXISTS deleted_at;
    """)
