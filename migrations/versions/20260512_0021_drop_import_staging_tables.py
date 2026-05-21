"""drop import staging tables

Revision ID: 20260512_0021
Revises: 20260512_0020
Create Date: 2026-05-12 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260512_0021"
down_revision: str | None = "20260512_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("import_staged_records")
    op.drop_table("import_raw_extractions")
    op.drop_table("import_source_files")


def downgrade() -> None:
    pass
