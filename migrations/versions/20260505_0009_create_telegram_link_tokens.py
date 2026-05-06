"""create telegram link tokens table

Revision ID: 20260505_0009
Revises: 20260429_0008
Create Date: 2026-05-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260505_0009"
down_revision: str | None = "20260429_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_link_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("token", sa.String(length=128), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_telegram_link_tokens_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_telegram_link_tokens_created_by_users"
        ),
    )
    op.create_index("ix_telegram_link_tokens_token", "telegram_link_tokens", ["token"])
    op.create_index("ix_telegram_link_tokens_user_id", "telegram_link_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_telegram_link_tokens_user_id", table_name="telegram_link_tokens")
    op.drop_index("ix_telegram_link_tokens_token", table_name="telegram_link_tokens")
    op.drop_table("telegram_link_tokens")
