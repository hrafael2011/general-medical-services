"""add mission assignment soft delete

Revision ID: 20260512_0020
Revises: 20260512_0019
Create Date: 2026-05-12 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260512_0020"
down_revision: str | None = "20260512_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mission_assignments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_mission_assignments_deleted_at",
        "mission_assignments",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mission_assignments_deleted_at", table_name="mission_assignments")
    op.drop_column("mission_assignments", "deleted_at")
