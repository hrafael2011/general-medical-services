"""add user doctor link

Revision ID: 20260514_0024
Revises: 20260513_0023
Create Date: 2026-05-14 08:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260514_0024"
down_revision: str | None = "20260513_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("doctor_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_users_doctor_id_doctors",
        "users",
        "doctors",
        ["doctor_id"],
        ["id"],
    )
    op.create_index("ix_users_doctor_id", "users", ["doctor_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_doctor_id", table_name="users")
    op.drop_constraint("fk_users_doctor_id_doctors", "users", type_="foreignkey")
    op.drop_column("users", "doctor_id")
