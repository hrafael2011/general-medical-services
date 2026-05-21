"""Add deleted_at to calendars

Revision ID: 20260521_0026
Revises: 20260516_0019
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260521_0026"
down_revision: str | None = "20260516_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: column may already exist if created by tests or Base.metadata.create_all()
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'calendars' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE calendars ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE calendars DROP COLUMN IF EXISTS deleted_at;
    """)
