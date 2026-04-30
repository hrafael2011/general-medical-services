"""create notifications and jobs

Revision ID: 20260429_0006
Revises: 20260429_0005
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0006"
down_revision: str | None = "20260429_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("recipient_doctor_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_phone", sa.String(length=30), nullable=True),
        sa.Column("assignment_id", sa.String(length=36), nullable=True),
        sa.Column("mission_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(length=30), nullable=True),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_doctor_id"], ["doctors.id"], name="fk_notification_events_recipient_doctor_id_doctors"),
        sa.ForeignKeyConstraint(["assignment_id"], ["calendar_assignments.id"], name="fk_notification_events_assignment_id_calendar_assignments"),
        sa.ForeignKeyConstraint(["mission_id"], ["mission_assignments.id"], name="fk_notification_events_mission_id_mission_assignments"),
    )
    op.create_index("ix_notification_events_status", "notification_events", ["status"])
    op.create_index("ix_notification_events_scheduled_for", "notification_events", ["scheduled_for"])
    op.create_index("ix_notification_events_recipient_doctor_id", "notification_events", ["recipient_doctor_id"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_token", sa.String(length=80), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduled_jobs_job_type", "scheduled_jobs", ["job_type"])
    op.create_index("ix_scheduled_jobs_status", "scheduled_jobs", ["status"])

    op.create_table(
        "job_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scheduled_job_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("items_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scheduled_job_id"], ["scheduled_jobs.id"], name="fk_job_executions_scheduled_job_id_scheduled_jobs"),
    )
    op.create_index("ix_job_executions_scheduled_job_id", "job_executions", ["scheduled_job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_executions_scheduled_job_id", table_name="job_executions")
    op.drop_table("job_executions")
    op.drop_index("ix_scheduled_jobs_status", table_name="scheduled_jobs")
    op.drop_index("ix_scheduled_jobs_job_type", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
    op.drop_index("ix_notification_events_recipient_doctor_id", table_name="notification_events")
    op.drop_index("ix_notification_events_scheduled_for", table_name="notification_events")
    op.drop_index("ix_notification_events_status", table_name="notification_events")
    op.drop_table("notification_events")
