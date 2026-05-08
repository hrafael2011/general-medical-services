"""Add missing created_at/updated_at to import tables

Revision ID: 20260507_0017
Revises: 20260507_0016
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0017"
down_revision: str | None = "20260507_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # import_source_files is missing created_at and updated_at
    op.add_column(
        "import_source_files",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "import_source_files",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # import_staged_records has created_at but is missing updated_at
    op.add_column(
        "import_staged_records",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill created_at from imported_at for existing rows
    op.execute(
        "UPDATE import_source_files SET created_at = imported_at WHERE created_at IS NULL"
    )
    op.execute(
        "UPDATE import_source_files SET updated_at = imported_at WHERE updated_at IS NULL"
    )
    op.execute(
        "UPDATE import_staged_records SET updated_at = created_at WHERE updated_at IS NULL"
    )

    # Make nullable=False now that data is backfilled
    op.alter_column("import_source_files", "created_at", nullable=False)
    op.alter_column("import_source_files", "updated_at", nullable=False)
    op.alter_column("import_staged_records", "updated_at", nullable=False)

    # Also fix column type mismatches between migration and model
    op.alter_column(
        "import_source_files",
        "parser_version",
        type_=sa.String(60),
        existing_type=sa.String(32),
        nullable=True,
    )
    op.alter_column(
        "import_source_files",
        "status",
        type_=sa.String(20),
        existing_type=sa.String(32),
        nullable=False,
        existing_server_default="pending",
    )
    op.alter_column(
        "import_staged_records",
        "record_type",
        type_=sa.String(100),
        existing_type=sa.String(32),
        nullable=False,
    )
    op.alter_column(
        "import_staged_records",
        "review_status",
        type_=sa.String(20),
        existing_type=sa.String(32),
        nullable=False,
        existing_server_default="pending",
    )


def downgrade() -> None:
    op.drop_column("import_source_files", "updated_at")
    op.drop_column("import_source_files", "created_at")
    op.drop_column("import_staged_records", "updated_at")
