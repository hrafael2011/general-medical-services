"""Add deleted_at to ranks and departments

Revision ID: 20260521_0031
Revises: 20260521_0030
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0031"
down_revision: str | None = "20260521_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ranks' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE ranks ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'departments' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE departments ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ranks DROP COLUMN IF EXISTS deleted_at;
        ALTER TABLE departments DROP COLUMN IF EXISTS deleted_at;
    """)
