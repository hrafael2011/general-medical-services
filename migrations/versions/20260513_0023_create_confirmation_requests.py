"""create confirmation requests

Revision ID: 20260513_0023
Revises: 20260513_0022
Create Date: 2026-05-13 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513_0023"
down_revision: str | None = "20260513_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "confirmation_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("confirmation_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=140), nullable=False),
        sa.Column("response_token", sa.String(length=80), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("notification_id", sa.String(length=36), nullable=True),
        sa.Column("assignment_id", sa.String(length=36), nullable=True),
        sa.Column("mission_id", sa.String(length=36), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_channel", sa.String(length=30), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["calendar_assignments.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["mission_id"], ["mission_assignments.id"]),
        sa.ForeignKeyConstraint(["notification_id"], ["notification_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("response_token"),
    )
    op.create_index("ix_confirmation_requests_assignment_id", "confirmation_requests", ["assignment_id"])
    op.create_index("ix_confirmation_requests_confirmation_type", "confirmation_requests", ["confirmation_type"])
    op.create_index("ix_confirmation_requests_created_at", "confirmation_requests", ["created_at"])
    op.create_index("ix_confirmation_requests_created_by", "confirmation_requests", ["created_by"])
    op.create_index("ix_confirmation_requests_doctor_id", "confirmation_requests", ["doctor_id"])
    op.create_index("ix_confirmation_requests_due_at", "confirmation_requests", ["due_at"])
    op.create_index("ix_confirmation_requests_mission_id", "confirmation_requests", ["mission_id"])
    op.create_index("ix_confirmation_requests_notification_id", "confirmation_requests", ["notification_id"])
    op.create_index("ix_confirmation_requests_status", "confirmation_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_confirmation_requests_status", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_notification_id", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_mission_id", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_due_at", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_doctor_id", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_created_by", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_created_at", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_confirmation_type", table_name="confirmation_requests")
    op.drop_index("ix_confirmation_requests_assignment_id", table_name="confirmation_requests")
    op.drop_table("confirmation_requests")
