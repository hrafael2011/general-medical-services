"""
DB-backed integration tests for ImportReviewService.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import UTC, datetime

from backend.app.application.import_pipeline.review_service import ImportReviewService
from backend.app.infrastructure.db.models.import_staging import (
    ImportSourceFileModel,
    ImportStagedRecordModel,
)
from backend.app.infrastructure.repositories.import_staging import ImportRepository

# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


def _make_review_service(db_session) -> ImportReviewService:
    return ImportReviewService(ImportRepository(db_session))


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------


def _seed_staged_record(db_session, review_status="pending") -> ImportStagedRecordModel:
    sf = ImportSourceFileModel(
        id=str(uuid.uuid4()),
        file_name="test.xlsx",
        file_type="xlsx",
        checksum=str(uuid.uuid4()),  # unique per call
        imported_at=datetime.now(UTC),
        status="processed",
        record_count=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(sf)
    db_session.flush()

    record = ImportStagedRecordModel(
        id=str(uuid.uuid4()),
        source_file_id=sf.id,
        record_type="doctor",
        raw_value="Dr. Test",
        confidence=0.8,
        review_status=review_status,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(record)
    db_session.flush()
    return record


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_review_approve(db_session) -> None:
    """Approving a record sets review_status='approved' and reviewed_by."""
    record = _seed_staged_record(db_session)
    service = _make_review_service(db_session)

    result = service.review_record(
        record_id=record.id,
        action="approve",
        reviewed_by="actor-1",
    )

    assert result["ok"] is True

    repo = ImportRepository(db_session)
    refreshed = repo.get_staged_record_by_id(record.id)
    assert refreshed is not None
    assert refreshed.review_status == "approved"
    assert refreshed.reviewed_by == "actor-1"


def test_review_reject(db_session) -> None:
    """Rejecting a record sets review_status='rejected'."""
    record = _seed_staged_record(db_session)
    service = _make_review_service(db_session)

    result = service.review_record(
        record_id=record.id,
        action="reject",
        reviewed_by="actor-2",
    )

    assert result["ok"] is True

    repo = ImportRepository(db_session)
    refreshed = repo.get_staged_record_by_id(record.id)
    assert refreshed is not None
    assert refreshed.review_status == "rejected"


def test_review_not_found(db_session) -> None:
    """Reviewing a non-existent record returns ok=False with error='not_found'."""
    service = _make_review_service(db_session)
    result = service.review_record(
        record_id="nonexistent",
        action="approve",
        reviewed_by="actor",
    )
    assert result["ok"] is False
    assert result["error"] == "not_found"


def test_apply_approved(db_session) -> None:
    """apply_approved() marks all approved records as 'applied' with applied_at set."""
    record = _seed_staged_record(db_session, review_status="pending")

    # Directly approve the record in the session
    record.review_status = "approved"
    db_session.flush()

    service = _make_review_service(db_session)
    result = service.apply_approved(applied_by="actor-1")

    assert result["applied"] == 1
    assert result["skipped"] == 0

    repo = ImportRepository(db_session)
    refreshed = repo.get_staged_record_by_id(record.id)
    assert refreshed is not None
    assert refreshed.review_status == "applied"
    assert refreshed.applied_at is not None
