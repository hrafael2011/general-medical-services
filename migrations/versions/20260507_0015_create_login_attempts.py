"""Create login_attempts table

Revision ID: 20260507_0015
Revises: 20260507_0014
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0015"
down_revision: str | None = "20260507_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ip_address", sa.String(45), nullable=False, index=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("success", sa.Boolean(), nullable=False, default=False),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
