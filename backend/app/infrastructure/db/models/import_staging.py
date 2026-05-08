from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.db.base import Base


class ImportSourceFileModel(Base):
    __tablename__ = "import_source_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    detected_period_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_period_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    parser_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    staged_records: Mapped[list["ImportStagedRecordModel"]] = relationship(
        "ImportStagedRecordModel", back_populates="source_file"
    )
    raw_extractions: Mapped[list["ImportRawExtractionModel"]] = relationship(
        "ImportRawExtractionModel", back_populates="source_file"
    )


class ImportRawExtractionModel(Base):
    __tablename__ = "import_raw_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_source_files.id"), nullable=False, index=True
    )
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cell_reference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    source_file: Mapped["ImportSourceFileModel"] = relationship(
        "ImportSourceFileModel", back_populates="raw_extractions"
    )


class ImportStagedRecordModel(Base):
    __tablename__ = "import_staged_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_file_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_source_files.id"), nullable=False, index=True
    )
    source_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    record_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    normalized_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    parser_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    match_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    matched_doctor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True, index=True
    )
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source_file: Mapped["ImportSourceFileModel"] = relationship(
        "ImportSourceFileModel", back_populates="staged_records"
    )
