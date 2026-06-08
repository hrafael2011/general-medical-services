"""add telegram_chat_id to doctors

Revision ID: 4ff8637a6872
Revises: 20260528_0042
Create Date: 2026-06-08 18:58:23.858450
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '4ff8637a6872'
down_revision: str | None = '20260528_0042'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('doctors', sa.Column('telegram_chat_id', sa.String(length=60), nullable=True))
    op.create_unique_constraint(op.f('uq_doctors_telegram_chat_id'), 'doctors', ['telegram_chat_id'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_doctors_telegram_chat_id'), 'doctors', type_='unique')
    op.drop_column('doctors', 'telegram_chat_id')
