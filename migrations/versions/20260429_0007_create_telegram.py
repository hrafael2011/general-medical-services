"""create telegram assistant module tables

Revision ID: 20260429_0007
Revises: 20260429_0006
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0007"
down_revision: str | None = "20260429_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_user_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("telegram_user_id", sa.String(length=60), nullable=False, unique=True),
        sa.Column("telegram_username", sa.String(length=120), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("linked_by", sa.String(length=36), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_telegram_user_links_user_id_users"),
    )
    op.create_index("ix_telegram_user_links_user_id", "telegram_user_links", ["user_id"])

    op.create_table(
        "telegram_interactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("telegram_user_id", sa.String(length=60), nullable=False),
        sa.Column("matched_user_id", sa.String(length=36), nullable=True),
        sa.Column("user_role", sa.String(length=20), nullable=True),
        sa.Column("intent_id", sa.String(length=80), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("extracted_entities", sa.JSON(), nullable=True),
        sa.Column("intent_confidence", sa.Float(), nullable=True),
        sa.Column("tool_name", sa.String(length=80), nullable=True),
        sa.Column("tool_request", sa.JSON(), nullable=True),
        sa.Column("tool_response", sa.JSON(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("cache_status", sa.String(length=20), nullable=True),
        sa.Column("fallback_reason", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["matched_user_id"], ["users.id"], name="fk_telegram_interactions_matched_user_id_users"),
    )
    op.create_index("ix_telegram_interactions_telegram_user_id", "telegram_interactions", ["telegram_user_id"])
    op.create_index("ix_telegram_interactions_matched_user_id", "telegram_interactions", ["matched_user_id"])
    op.create_index("ix_telegram_interactions_intent_id", "telegram_interactions", ["intent_id"])


def downgrade() -> None:
    op.drop_index("ix_telegram_interactions_intent_id", table_name="telegram_interactions")
    op.drop_index("ix_telegram_interactions_matched_user_id", table_name="telegram_interactions")
    op.drop_index("ix_telegram_interactions_telegram_user_id", table_name="telegram_interactions")
    op.drop_table("telegram_interactions")
    op.drop_index("ix_telegram_user_links_user_id", table_name="telegram_user_links")
    op.drop_table("telegram_user_links")
