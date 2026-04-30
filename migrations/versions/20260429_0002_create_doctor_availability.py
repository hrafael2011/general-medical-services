"""create doctor availability

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0002"
down_revision: str | None = "20260429_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doctor_availability",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("availability_type", sa.String(length=30), nullable=False),
        sa.Column("days_of_week", sa.JSON(), nullable=True),
        sa.Column("available_dates", sa.JSON(), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("week_number", sa.Integer(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="approved"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["doctors.id"],
            name="fk_doctor_availability_doctor_id_doctors",
        ),
    )
    op.create_index("ix_doctor_availability_doctor_id", "doctor_availability", ["doctor_id"])
    op.create_index("ix_doctor_availability_type", "doctor_availability", ["availability_type"])
    op.create_index(
        "ix_doctor_availability_doctor_year_month",
        "doctor_availability",
        ["doctor_id", "year", "month"],
    )

    op.create_table(
        "doctor_restrictions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("reason_id", sa.String(length=36), nullable=True),
        sa.Column("restriction_type", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("ends_at", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="approved"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifted_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["doctor_id"], ["doctors.id"],
            name="fk_doctor_restrictions_doctor_id_doctors",
        ),
        sa.ForeignKeyConstraint(
            ["reason_id"], ["deactivation_reasons.id"],
            name="fk_doctor_restrictions_reason_id_deactivation_reasons",
        ),
    )
    op.create_index("ix_doctor_restrictions_doctor_id", "doctor_restrictions", ["doctor_id"])
    op.create_index("ix_doctor_restrictions_starts_at", "doctor_restrictions", ["starts_at"])


def downgrade() -> None:
    op.drop_index("ix_doctor_restrictions_starts_at", table_name="doctor_restrictions")
    op.drop_index("ix_doctor_restrictions_doctor_id", table_name="doctor_restrictions")
    op.drop_table("doctor_restrictions")

    op.drop_index("ix_doctor_availability_doctor_year_month", table_name="doctor_availability")
    op.drop_index("ix_doctor_availability_type", table_name="doctor_availability")
    op.drop_index("ix_doctor_availability_doctor_id", table_name="doctor_availability")
    op.drop_table("doctor_availability")
