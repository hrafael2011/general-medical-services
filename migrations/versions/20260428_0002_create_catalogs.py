"""create catalogs

Revision ID: 20260428_0002
Revises: 20260428_0001
Create Date: 2026-04-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260428_0002"
down_revision: str | None = "20260428_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_areas",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("required_for_daily_coverage", sa.Boolean(), nullable=False),
        sa.Column("load_weight", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_service_areas_code"),
    )
    op.create_index("ix_service_areas_code", "service_areas", ["code"])

    op.create_table(
        "ranks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("abbreviation", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_ranks_normalized_name"),
    )
    op.create_index("ix_ranks_normalized_name", "ranks", ["normalized_name"])

    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_departments_normalized_name"),
    )
    op.create_index("ix_departments_normalized_name", "departments", ["normalized_name"])

    op.create_table(
        "deactivation_reasons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("requires_detail", sa.Boolean(), nullable=False),
        sa.Column("applies_to_sex", sa.String(length=20), nullable=True),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_deactivation_reasons_code"),
    )
    op.create_index("ix_deactivation_reasons_code", "deactivation_reasons", ["code"])

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=120), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index("ix_deactivation_reasons_code", table_name="deactivation_reasons")
    op.drop_table("deactivation_reasons")
    op.drop_index("ix_departments_normalized_name", table_name="departments")
    op.drop_table("departments")
    op.drop_index("ix_ranks_normalized_name", table_name="ranks")
    op.drop_table("ranks")
    op.drop_index("ix_service_areas_code", table_name="service_areas")
    op.drop_table("service_areas")

