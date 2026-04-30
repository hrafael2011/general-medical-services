"""
Full import pipeline orchestration service.
Coordinates extraction → staging → identity resolution → quality report.
"""

from datetime import UTC, datetime
from uuid import uuid4

from backend.app.application.import_pipeline.extractor import (
    compute_checksum,
    extract_file,
    is_lock_file,
)
from backend.app.application.import_pipeline.identity_resolver import resolve_identity
from backend.app.application.import_pipeline.normalizer import classify_cell, normalize_name
from backend.app.infrastructure.db.models.import_staging import (
    ImportRawExtractionModel,
    ImportSourceFileModel,
    ImportStagedRecordModel,
)
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.import_staging import ImportRepository

# Marker types that map directly to record_type
_MARKER_RECORD_TYPES = {
    "license",
    "restriction",
    "monthly_limit",
    "monthly_target",
    "fixed_availability",
}


class ImportPipelineService:
    PARSER_VERSION = "1.0"

    def __init__(
        self,
        import_repo: ImportRepository,
        doctor_repo: DoctorRepository,
    ) -> None:
        self._import_repo = import_repo
        self._doctor_repo = doctor_repo

    # ── Public API ────────────────────────────────────────────────────────────

    def register_and_process(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        imported_by: str | None = None,
        detected_period_year: int | None = None,
        detected_period_month: int | None = None,
    ) -> dict:
        """
        Full pipeline for a single file. Returns quality report dict.

        Steps:
          1. Skip Office lock files.
          2. Deduplicate by SHA-256 checksum.
          3. Register ImportSourceFileModel (status="processing").
          4. Extract raw cells/lines from the file.
          5. Persist raw extractions in bulk.
          6. Classify each extraction and resolve doctor identity.
          7. Persist staged records in bulk.
          8. Mark source file as "processed".
          9. Return quality report.
        On any exception: mark source file as "failed" and re-raise.
        """
        # Step 1 — skip lock files
        if is_lock_file(file_name):
            return {"ignored": True, "reason": "lock_file"}

        # Step 2 — duplicate check
        checksum = compute_checksum(file_bytes)
        existing = self._import_repo.get_source_file_by_checksum(checksum)
        if existing is not None:
            return {
                "ignored": True,
                "reason": "duplicate_checksum",
                "source_file_id": existing.id,
            }

        # Step 3 — register source file
        now = datetime.now(UTC)
        source_file = ImportSourceFileModel(
            id=str(uuid4()),
            file_name=file_name,
            file_path=None,
            file_type="unknown",  # will be updated after extraction
            checksum=checksum,
            detected_period_year=detected_period_year,
            detected_period_month=detected_period_month,
            imported_by=imported_by,
            imported_at=now,
            parser_version=self.PARSER_VERSION,
            status="processing",
            record_count=0,
            created_at=now,
            updated_at=now,
        )
        self._import_repo.add_source_file(source_file)

        try:
            # Step 4 — extract
            extractions_data, file_type = extract_file(file_bytes, file_name, source_file.id)
            source_file.file_type = file_type

            # Step 5 — build + persist raw extractions
            raw_models = [
                ImportRawExtractionModel(
                    id=str(uuid4()),
                    source_file_id=source_file.id,
                    sheet_name=ext.get("sheet_name"),
                    page_number=ext.get("page_number"),
                    row_number=ext.get("row_number"),
                    column_name=ext.get("column_name"),
                    cell_reference=ext.get("cell_reference"),
                    raw_value=ext.get("raw_value"),
                    extraction_method=ext.get("extraction_method"),
                    created_at=now,
                )
                for ext in extractions_data
            ]
            self._import_repo.bulk_add_raw_extractions(raw_models)

            # Step 6 — load doctors for identity resolution
            known_doctors = self._doctor_repo.list_all(active_only=False)

            # Step 7 — classify and stage
            staged_records: list[ImportStagedRecordModel] = []

            for ext in extractions_data:
                raw_value = ext.get("raw_value") or ""
                classification = classify_cell(raw_value)

                field = classification["field"]
                confidence = classification["confidence"]

                # Skip truly empty or very-low-confidence unknowns
                if field is None:
                    continue
                if field in ("empty", "unknown") and confidence < 0.3:
                    continue

                # Determine record_type
                if field == "doctor_name":
                    record_type = "doctor"
                elif field == "service_area":
                    record_type = "assignment"
                elif field == "marker":
                    parsed = classification["parsed_value"]
                    marker_type = parsed.get("type") if isinstance(parsed, dict) else None
                    record_type = marker_type if marker_type in _MARKER_RECORD_TYPES else "other"
                elif field == "rank":
                    record_type = "rank"
                elif field in ("day_number", "numeric"):
                    record_type = "other"
                else:
                    record_type = "other"

                # Identity resolution
                if record_type == "doctor":
                    matched_doctor_id, match_status = resolve_identity(
                        classification["parsed_value"],
                        known_doctors,
                    )
                    normalized_value = {"normalized_name": normalize_name(raw_value)}
                else:
                    matched_doctor_id = None
                    match_status = "unmatched"
                    normalized_value = None

                staged = ImportStagedRecordModel(
                    id=str(uuid4()),
                    source_file_id=source_file.id,
                    source_location={
                        "sheet": ext.get("sheet_name"),
                        "row": ext.get("row_number"),
                        "col": ext.get("column_name"),
                        "cell_ref": ext.get("cell_reference"),
                    },
                    record_type=record_type,
                    raw_value=raw_value,
                    parsed_value={
                        "field": field,
                        "value": classification["parsed_value"],
                    },
                    normalized_value=normalized_value,
                    confidence=confidence,
                    parser_rule=classification["parser_rule"],
                    match_status=match_status,
                    matched_doctor_id=matched_doctor_id,
                    review_status="pending",
                    created_at=now,
                    updated_at=now,
                )
                staged_records.append(staged)

            self._import_repo.bulk_add_staged_records(staged_records)

            # Step 8 — mark processed
            self._import_repo.update_source_file_status(
                source_file.id,
                "processed",
                record_count=len(staged_records),
            )

        except Exception as exc:
            self._import_repo.update_source_file_status(
                source_file.id,
                "failed",
                error_message=str(exc),
            )
            raise

        # Step 9 — return quality report
        return self.get_quality_report(source_file.id)

    def get_quality_report(self, source_file_id: str) -> dict | None:
        """Build quality report dict from DB data. Returns None if not found."""
        source_file = self._import_repo.get_source_file_by_id(source_file_id)
        if source_file is None:
            return None

        raw_count = len(self._import_repo.list_raw_extractions(source_file_id))
        staged = self._import_repo.list_staged_records(source_file_id=source_file_id)
        by_review = self._import_repo.count_staged_by_status(source_file_id)
        by_match = self._import_repo.count_staged_by_match_status(source_file_id)
        low_conf = sum(
            1 for s in staged if s.confidence is not None and s.confidence < 0.75
        )

        return {
            "source_file_id": source_file_id,
            "file_name": source_file.file_name,
            "total_raw_extractions": raw_count,
            "total_staged": len(staged),
            "exact_matches": by_match.get("exact_match", 0),
            "probable_matches": by_match.get("probable_match", 0),
            "possible_matches": by_match.get("possible_match", 0),
            "new_candidates": by_match.get("new_candidate", 0),
            "conflicts": by_match.get("conflict", 0),
            "low_confidence": low_conf,
            "pending_review": by_review.get("pending", 0),
            "approved": by_review.get("approved", 0),
            "rejected": by_review.get("rejected", 0),
            "applied": by_review.get("applied", 0),
        }
