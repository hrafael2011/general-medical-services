"""create audit_events

Revision ID: 20260429_0003
Revises: 20260429_0002
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0003"
down_revision: str | None = "20260429_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action_type", "audit_events", ["action_type"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_type", table_name="audit_events")
    op.drop_index("ix_audit_events_action_type", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_table("audit_events")
