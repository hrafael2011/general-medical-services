"""add telegram_sessions table

Revision ID: 58fd13f136af
Revises: 20260514_0025
Create Date: 2026-05-14 11:46:07.030605
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '58fd13f136af'
down_revision: str | None = '20260514_0025'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "telegram_sessions" in inspector.get_table_names():
        return

    op.create_table('telegram_sessions',
    sa.Column('telegram_user_id', sa.String(length=60), nullable=False),
    sa.Column('session_state', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('telegram_user_id', name=op.f('pk_telegram_sessions'))
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "telegram_sessions" in inspector.get_table_names():
        op.drop_table('telegram_sessions')
