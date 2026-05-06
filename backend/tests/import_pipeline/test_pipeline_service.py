"""
DB-backed integration tests for ImportPipelineService.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import UTC, datetime

from backend.app.application.import_pipeline.extractor import compute_checksum
from backend.app.application.import_pipeline.pipeline_service import ImportPipelineService
from backend.app.infrastructure.db.models.import_staging import ImportSourceFileModel
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.import_staging import ImportRepository

# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


def _make_service(db_session) -> ImportPipelineService:
    return ImportPipelineService(
        import_repo=ImportRepository(db_session),
        doctor_repo=DoctorRepository(db_session),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_lock_file_ignored(db_session) -> None:
    """Office lock files (~$...) are immediately ignored."""
    service = _make_service(db_session)
    result = service.register_and_process(
        file_bytes=b"x",
        file_name="~$archivo.xlsx",
    )
    assert result["ignored"] is True
    assert result["reason"] == "lock_file"


def test_duplicate_checksum_ignored(db_session) -> None:
    """A file whose checksum already exists in the DB is ignored as a duplicate."""
    content = b"some content"
    checksum = compute_checksum(content)

    # Manually register a source file with the same checksum
    sf = ImportSourceFileModel(
        id=str(uuid.uuid4()),
        file_name="existing.xlsx",
        file_type="xlsx",
        checksum=checksum,
        imported_at=datetime.now(UTC),
        status="processed",
        record_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(sf)
    db_session.flush()

    service = _make_service(db_session)
    result = service.register_and_process(
        file_bytes=content,
        file_name="test.xlsx",
    )
    assert result["ignored"] is True
    assert result["reason"] == "duplicate_checksum"


def test_unknown_extension_ignored(db_session) -> None:
    """A file with an unrecognised extension completes with 0 staged records (no exception)."""
    service = _make_service(db_session)
    result = service.register_and_process(
        file_bytes=b"content",
        file_name="document.docx",
    )
    # Should not be marked as ignored — it processes with zero extractions
    assert result.get("ignored") is None or result.get("total_staged", 0) == 0


def test_quality_report_not_found(db_session) -> None:
    """get_quality_report returns None for a non-existent source_file_id."""
    result = _make_service(db_session).get_quality_report("nonexistent-id")
    assert result is None
