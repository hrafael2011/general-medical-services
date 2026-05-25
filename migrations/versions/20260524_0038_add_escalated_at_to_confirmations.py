"""Add escalated_at column to confirmation_requests table

Revision ID: 20260524_0038
Revises: 20260524_0037
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0038"
down_revision: str | None = "20260524_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE confirmation_requests
        ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMP WITH TIME ZONE;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_confirmation_requests_escalated_at
        ON confirmation_requests (escalated_at);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS ix_confirmation_requests_escalated_at;
    """)
    op.execute("""
        ALTER TABLE confirmation_requests
        DROP COLUMN IF EXISTS escalated_at;
    """)
