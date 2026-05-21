"""Add deleted_at to users

Revision ID: 20260521_0030
Revises: 20260521_0029
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0030"
down_revision: str | None = "20260521_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;")
