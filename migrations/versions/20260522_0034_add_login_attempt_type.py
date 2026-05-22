"""Add attempt_type to login_attempts

Revision ID: 20260522_0034
Revises: 20260521_0033
Create Date: 2026-05-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260522_0034"
down_revision: str | None = "20260521_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE login_attempts
        ADD COLUMN IF NOT EXISTS attempt_type VARCHAR(20);

        UPDATE login_attempts
        SET attempt_type = 'login'
        WHERE attempt_type IS NULL;

        ALTER TABLE login_attempts
        ALTER COLUMN attempt_type SET DEFAULT 'login',
        ALTER COLUMN attempt_type SET NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE login_attempts
        DROP COLUMN IF EXISTS attempt_type;
    """)
