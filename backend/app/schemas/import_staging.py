from datetime import datetime

from pydantic import BaseModel

# --- Import Source File ---

class ImportSourceFileRead(BaseModel):
    id: str
    file_name: str
    file_path: str | None
    file_type: str
    checksum: str
    detected_period_year: int | None
    detected_period_month: int | None
    imported_by: str | None
    imported_at: datetime
    parser_version: str | None
    status: str
    record_count: int
    error_message: str | None

    model_config = {"from_attributes": True}


class ImportSourceFileListResponse(BaseModel):
    items: list[ImportSourceFileRead]
    total: int


# --- Import Staged Record ---

class ImportStagedRecordRead(BaseModel):
    id: str
    source_file_id: str
    source_location: dict | None
    record_type: str
    raw_value: str | None
    parsed_value: dict | None
    normalized_value: dict | None
    confidence: float | None
    parser_rule: str | None
    match_status: str | None
    matched_doctor_id: str | None
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    applied_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportStagedRecordListResponse(BaseModel):
    items: list[ImportStagedRecordRead]
    total: int


# --- Review and Apply Requests ---

class ReviewStagedRecordRequest(BaseModel):
    action: str
    notes: str | None = None
    matched_doctor_id: str | None = None


class ApplyApprovedRequest(BaseModel):
    source_file_id: str | None = None


# --- Quality Report ---

class ImportQualityReport(BaseModel):
    source_file_id: str
    file_name: str
    total_raw_extractions: int
    total_staged: int
    exact_matches: int
    probable_matches: int
    possible_matches: int
    new_candidates: int
    conflicts: int
    low_confidence: int
    pending_review: int
    approved: int
    rejected: int
    applied: int

    model_config = {"from_attributes": True}
