"""add telegram_chat_id to users

Revision ID: 41f25b95c60a
Revises: 4ff8637a6872
Create Date: 2026-06-10 08:56:20.130797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41f25b95c60a'
down_revision: Union[str, None] = '4ff8637a6872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('telegram_chat_id', sa.String(length=60), nullable=True))
    op.create_unique_constraint(op.f('uq_users_telegram_chat_id'), 'users', ['telegram_chat_id'])


def downgrade() -> None:
    op.drop_constraint(op.f('uq_users_telegram_chat_id'), 'users', type_='unique')
    op.drop_column('users', 'telegram_chat_id')
