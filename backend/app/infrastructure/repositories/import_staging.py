from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.import_staging import (
    ImportRawExtractionModel,
    ImportSourceFileModel,
    ImportStagedRecordModel,
)


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # Source files
    def add_source_file(self, record: ImportSourceFileModel) -> ImportSourceFileModel:
        self.session.add(record)
        self.session.flush()
        return record

    def get_source_file_by_id(self, file_id: str) -> ImportSourceFileModel | None:
        return self.session.get(ImportSourceFileModel, file_id)

    def get_source_file_by_checksum(self, checksum: str) -> ImportSourceFileModel | None:
        stmt = select(ImportSourceFileModel).where(
            ImportSourceFileModel.checksum == checksum
        )
        return self.session.scalars(stmt).first()

    def list_source_files(self, limit: int = 100) -> list[ImportSourceFileModel]:
        stmt = (
            select(ImportSourceFileModel)
            .order_by(ImportSourceFileModel.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def update_source_file_status(
        self,
        file_id: str,
        status: str,
        record_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        source_file = self.session.get(ImportSourceFileModel, file_id)
        if source_file:
            source_file.status = status
            source_file.record_count = record_count
            source_file.error_message = error_message
            self.session.flush()

    # Raw extractions
    def add_raw_extraction(self, record: ImportRawExtractionModel) -> ImportRawExtractionModel:
        self.session.add(record)
        self.session.flush()
        return record

    def bulk_add_raw_extractions(self, records: list[ImportRawExtractionModel]) -> int:
        self.session.add_all(records)
        self.session.flush()
        return len(records)

    def list_raw_extractions(self, source_file_id: str) -> list[ImportRawExtractionModel]:
        stmt = (
            select(ImportRawExtractionModel)
            .where(ImportRawExtractionModel.source_file_id == source_file_id)
            .order_by(ImportRawExtractionModel.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    # Staged records
    def add_staged_record(self, record: ImportStagedRecordModel) -> ImportStagedRecordModel:
        self.session.add(record)
        self.session.flush()
        return record

    def bulk_add_staged_records(self, records: list[ImportStagedRecordModel]) -> int:
        self.session.add_all(records)
        self.session.flush()
        return len(records)

    def get_staged_record_by_id(self, record_id: str) -> ImportStagedRecordModel | None:
        return self.session.get(ImportStagedRecordModel, record_id)

    def list_staged_records(
        self,
        source_file_id: str | None = None,
        record_type: str | None = None,
        review_status: str | None = None,
        limit: int = 500,
    ) -> list[ImportStagedRecordModel]:
        stmt = select(ImportStagedRecordModel).order_by(
            ImportStagedRecordModel.created_at.desc()
        )
        if source_file_id:
            stmt = stmt.where(ImportStagedRecordModel.source_file_id == source_file_id)
        if record_type:
            stmt = stmt.where(ImportStagedRecordModel.record_type == record_type)
        if review_status:
            stmt = stmt.where(ImportStagedRecordModel.review_status == review_status)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count_staged_by_status(self, source_file_id: str) -> dict[str, int]:
        stmt = select(
            ImportStagedRecordModel.review_status,
            func.count(ImportStagedRecordModel.id).label("count"),
        ).where(ImportStagedRecordModel.source_file_id == source_file_id)
        stmt = stmt.group_by(ImportStagedRecordModel.review_status)
        results = self.session.execute(stmt).all()
        return {status: count for status, count in results}

    def count_staged_by_match_status(self, source_file_id: str) -> dict[str, int]:
        stmt = select(
            ImportStagedRecordModel.match_status,
            func.count(ImportStagedRecordModel.id).label("count"),
        ).where(ImportStagedRecordModel.source_file_id == source_file_id)
        stmt = stmt.group_by(ImportStagedRecordModel.match_status)
        results = self.session.execute(stmt).all()
        return {match_status: count for match_status, count in results if match_status}
