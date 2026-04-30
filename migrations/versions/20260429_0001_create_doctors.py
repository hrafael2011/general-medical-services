"""create doctors

Revision ID: 20260429_0001
Revises: 20260428_0002
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0001"
down_revision: str | None = "20260428_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sex", sa.String(length=10), nullable=False),
        sa.Column("rank_id", sa.String(length=36), nullable=True),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("service_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("service_inactive_reason_id", sa.String(length=36), nullable=True),
        sa.Column("service_inactive_detail", sa.String(length=500), nullable=True),
        sa.Column("participa_misiones", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("whatsapp_phone", sa.String(length=40), nullable=True),
        sa.Column("monthly_service_target", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("monthly_service_max", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("monthly_service_limit_mode", sa.String(length=20), nullable=False, server_default="warn_only"),
        sa.Column("availability_mode", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["rank_id"], ["ranks.id"], name="fk_doctors_rank_id_ranks"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_doctors_department_id_departments"),
        sa.ForeignKeyConstraint(["service_inactive_reason_id"], ["deactivation_reasons.id"], name="fk_doctors_service_inactive_reason_id_deactivation_reasons"),
    )
    op.create_index("ix_doctors_active", "doctors", ["active"])
    op.create_index("ix_doctors_service_active", "doctors", ["service_active"])
    op.create_index("ix_doctors_sex", "doctors", ["sex"])

    op.create_table(
        "doctor_allowed_areas",
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("service_area_id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("doctor_id", "service_area_id"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], name="fk_doctor_allowed_areas_doctor_id_doctors"),
        sa.ForeignKeyConstraint(["service_area_id"], ["service_areas.id"], name="fk_doctor_allowed_areas_service_area_id_service_areas"),
    )


def downgrade() -> None:
    op.drop_table("doctor_allowed_areas")
    op.drop_index("ix_doctors_sex", table_name="doctors")
    op.drop_index("ix_doctors_service_active", table_name="doctors")
    op.drop_index("ix_doctors_active", table_name="doctors")
    op.drop_table("doctors")
