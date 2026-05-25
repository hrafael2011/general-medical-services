"""Designate inghendrickrafael@gmail.com as superadmin

Revision ID: 20260524_0039
Revises: 20260524_0038
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0039"
down_revision: str | None = "20260524_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE users
        SET is_superadmin = TRUE
        WHERE email = 'inghendrickrafael@gmail.com'
          AND deleted_at IS NULL;
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE users
        SET is_superadmin = FALSE
        WHERE email = 'inghendrickrafael@gmail.com';
    """)
