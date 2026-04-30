"""
Review service for import staged records.
Handles approve/reject/needs_more_info transitions and bulk apply.
"""

from datetime import UTC, datetime

from backend.app.infrastructure.repositories.import_staging import ImportRepository


class ImportReviewService:
    def __init__(self, import_repo: ImportRepository) -> None:
        self._import_repo = import_repo

    def review_record(
        self,
        *,
        record_id: str,
        action: str,
        reviewed_by: str,
        notes: str | None = None,
        matched_doctor_id: str | None = None,
    ) -> dict:
        """
        Update review_status for a single staged record.

        Valid actions: "approve", "reject", "needs_more_info".
        Returns {"ok": True, "record_id": ...} on success,
                {"ok": False, "error": ...} on failure.
        Caller must commit the session.
        """
        record = self._import_repo.get_staged_record_by_id(record_id)
        if record is None:
            return {"ok": False, "error": "not_found"}

        valid_actions = {"approve", "reject", "needs_more_info"}
        if action not in valid_actions:
            return {"ok": False, "error": f"invalid_action: {action}"}

        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "needs_more_info": "needs_more_info",
        }

        record.review_status = status_map[action]
        record.reviewed_by = reviewed_by
        record.reviewed_at = datetime.now(UTC)

        if notes is not None:
            record.notes = notes
        if matched_doctor_id is not None:
            record.matched_doctor_id = matched_doctor_id

        return {"ok": True, "record_id": record_id}

    def apply_approved(
        self,
        *,
        source_file_id: str | None = None,
        applied_by: str,
    ) -> dict:
        """
        Mark all approved staged records as "applied".
        Canonical writes are deferred to a future phase.

        Returns {"applied": int, "skipped": int, "errors": list[str]}.
        Caller must commit the session.
        """
        records = self._import_repo.list_staged_records(
            source_file_id=source_file_id,
            review_status="approved",
        )

        applied = 0
        skipped = 0
        errors: list[str] = []
        now = datetime.now(UTC)

        for record in records:
            try:
                record.review_status = "applied"
                record.applied_at = now
                applied += 1
            except Exception as exc:
                errors.append(f"{record.id}: {exc}")
                skipped += 1

        return {"applied": applied, "skipped": skipped, "errors": errors}
