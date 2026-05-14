"""create action alerts

Revision ID: 20260513_0022
Revises: 20260512_0021
Create Date: 2026-05-13 09:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513_0022"
down_revision: str | None = "20260512_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("alert_type", sa.String(length=80), nullable=False),
        sa.Column("section", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=True),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("action_url", sa.String(length=250), nullable=True),
        sa.Column("alert_metadata", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["dismissed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_alerts_alert_type", "action_alerts", ["alert_type"])
    op.create_index("ix_action_alerts_created_at", "action_alerts", ["created_at"])
    op.create_index("ix_action_alerts_created_by", "action_alerts", ["created_by"])
    op.create_index("ix_action_alerts_dismissed_by", "action_alerts", ["dismissed_by"])
    op.create_index("ix_action_alerts_entity_id", "action_alerts", ["entity_id"])
    op.create_index("ix_action_alerts_entity_type", "action_alerts", ["entity_type"])
    op.create_index("ix_action_alerts_resolved_by", "action_alerts", ["resolved_by"])
    op.create_index("ix_action_alerts_section", "action_alerts", ["section"])
    op.create_index("ix_action_alerts_severity", "action_alerts", ["severity"])
    op.create_index("ix_action_alerts_status", "action_alerts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_action_alerts_status", table_name="action_alerts")
    op.drop_index("ix_action_alerts_severity", table_name="action_alerts")
    op.drop_index("ix_action_alerts_section", table_name="action_alerts")
    op.drop_index("ix_action_alerts_resolved_by", table_name="action_alerts")
    op.drop_index("ix_action_alerts_entity_type", table_name="action_alerts")
    op.drop_index("ix_action_alerts_entity_id", table_name="action_alerts")
    op.drop_index("ix_action_alerts_dismissed_by", table_name="action_alerts")
    op.drop_index("ix_action_alerts_created_by", table_name="action_alerts")
    op.drop_index("ix_action_alerts_created_at", table_name="action_alerts")
    op.drop_index("ix_action_alerts_alert_type", table_name="action_alerts")
    op.drop_table("action_alerts")
