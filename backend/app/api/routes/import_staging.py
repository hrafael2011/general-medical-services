from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.import_pipeline.pipeline_service import ImportPipelineService
from backend.app.application.import_pipeline.review_service import ImportReviewService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.import_staging import ImportRepository
from backend.app.schemas.import_staging import (
    ApplyApprovedRequest,
    ImportSourceFileListResponse,
    ImportSourceFileRead,
    ImportStagedRecordListResponse,
    ImportStagedRecordRead,
    ReviewStagedRecordRequest,
)

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/upload")
async def upload_import_file(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    file: UploadFile = File(...),
    year: int | None = Query(None),
    month: int | None = Query(None),
) -> dict:
    file_bytes = await file.read()
    service = ImportPipelineService(
        ImportRepository(session),
        DoctorRepository(session),
    )
    result = service.register_and_process(
        file_bytes=file_bytes,
        file_name=file.filename,
        imported_by=_user.id,
        detected_period_year=year,
        detected_period_month=month,
    )
    session.commit()
    return result


@router.get("/files", response_model=ImportSourceFileListResponse)
def list_import_files(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ImportSourceFileListResponse:
    items = ImportRepository(session).list_source_files(limit=200)
    return ImportSourceFileListResponse(
        items=[ImportSourceFileRead.model_validate(f) for f in items],
        total=len(items),
    )


@router.get("/files/{file_id}/quality-report")
def get_quality_report(
    file_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    service = ImportPipelineService(
        ImportRepository(session),
        DoctorRepository(session),
    )
    report = service.get_quality_report(file_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Source file not found")
    return report


@router.get("/staged", response_model=ImportStagedRecordListResponse)
def list_staged_records(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    source_file_id: str | None = Query(None),
    record_type: str | None = Query(None),
    review_status: str | None = Query(None),
    limit: int = Query(200, le=1000),
) -> ImportStagedRecordListResponse:
    items = ImportRepository(session).list_staged_records(
        source_file_id=source_file_id,
        record_type=record_type,
        review_status=review_status,
        limit=limit,
    )
    return ImportStagedRecordListResponse(
        items=[ImportStagedRecordRead.model_validate(r) for r in items],
        total=len(items),
    )


@router.post("/staged/{record_id}/review", response_model=ImportStagedRecordRead)
def review_staged_record(
    record_id: str,
    body: ReviewStagedRecordRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ImportStagedRecordRead:
    service = ImportReviewService(ImportRepository(session))
    result = service.review_record(
        record_id=record_id,
        action=body.action,
        reviewed_by=_user.id,
        notes=body.notes,
        matched_doctor_id=body.matched_doctor_id,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    session.commit()
    updated = ImportRepository(session).get_staged_record_by_id(record_id)
    return ImportStagedRecordRead.model_validate(updated)


@router.post("/apply")
def apply_approved_records(
    body: ApplyApprovedRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    service = ImportReviewService(ImportRepository(session))
    result = service.apply_approved(
        source_file_id=body.source_file_id,
        applied_by=_user.id,
    )
    session.commit()
    return result
