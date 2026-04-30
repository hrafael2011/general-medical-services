"""create import staging tables

Revision ID: 20260429_0008
Revises: 20260429_0007
Create Date: 2026-04-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260429_0008"
down_revision: str | None = "20260429_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_source_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False, unique=True),
        sa.Column("detected_period_year", sa.Integer(), nullable=True),
        sa.Column("detected_period_month", sa.Integer(), nullable=True),
        sa.Column("imported_by", sa.String(length=36), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("parser_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], name="fk_import_source_files_imported_by_users", ondelete="SET NULL"),
    )
    op.create_index("ix_import_source_files_checksum", "import_source_files", ["checksum"])
    op.create_index("ix_import_source_files_status", "import_source_files", ["status"])

    op.create_table(
        "import_raw_extractions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("sheet_name", sa.String(length=256), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("column_name", sa.String(length=256), nullable=True),
        sa.Column("cell_reference", sa.String(length=32), nullable=True),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_file_id"], ["import_source_files.id"], name="fk_import_raw_extractions_source_file_id_import_source_files", ondelete="CASCADE"),
    )
    op.create_index("ix_import_raw_extractions_source_file_id", "import_raw_extractions", ["source_file_id"])

    op.create_table(
        "import_staged_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("source_location", sa.JSON(), nullable=True),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("parsed_value", sa.JSON(), nullable=True),
        sa.Column("normalized_value", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("parser_rule", sa.String(length=128), nullable=True),
        sa.Column("match_status", sa.String(length=32), nullable=True),
        sa.Column("matched_doctor_id", sa.String(length=36), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_file_id"], ["import_source_files.id"], name="fk_import_staged_records_source_file_id_import_source_files", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_doctor_id"], ["doctors.id"], name="fk_import_staged_records_matched_doctor_id_doctors", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], name="fk_import_staged_records_reviewed_by_users", ondelete="SET NULL"),
    )
    op.create_index("ix_import_staged_records_source_file_id", "import_staged_records", ["source_file_id"])
    op.create_index("ix_import_staged_records_review_status", "import_staged_records", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_import_staged_records_review_status", table_name="import_staged_records")
    op.drop_index("ix_import_staged_records_source_file_id", table_name="import_staged_records")
    op.drop_table("import_staged_records")
    op.drop_index("ix_import_raw_extractions_source_file_id", table_name="import_raw_extractions")
    op.drop_table("import_raw_extractions")
    op.drop_index("ix_import_source_files_status", table_name="import_source_files")
    op.drop_index("ix_import_source_files_checksum", table_name="import_source_files")
    op.drop_table("import_source_files")
