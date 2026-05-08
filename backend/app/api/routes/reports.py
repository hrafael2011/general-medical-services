import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.reports.report_service import ReportService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.infrastructure.repositories.notifications import NotificationRepository

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> ReportService:
    return ReportService(
        calendar_repo=CalendarRepository(session),
        notification_repo=NotificationRepository(session),
        doctor_repo=DoctorRepository(session),
        mission_repo=MissionRepository(session),
        catalog_repo=CatalogRepository(session),
    )


@router.get("/calendar/{calendar_id}/excel")
def get_calendar_excel(
    calendar_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> StreamingResponse:
    try:
        data = service.generate_calendar_excel(calendar_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="calendario_{calendar_id[:8]}.xlsx"'
        },
    )


@router.get("/doctor-history/excel")
def get_doctor_history_excel(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> StreamingResponse:
    try:
        data = service.generate_doctor_history_excel(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="historial_{year}_{month}.xlsx"'
        },
    )


@router.get("/notifications-summary")
def get_notifications_summary(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> dict:
    return service.generate_notifications_summary(year, month)


@router.get("/operational-summary")
def get_operational_summary(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> dict:
    return service.generate_operational_summary(year, month)


@router.get("/weekly-schedule")
def get_weekly_schedule(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    calendar_version_id: str | None = None,
) -> StreamingResponse:
    try:
        data = service.build_weekly_schedule(year=year, month=month, calendar_version_id=calendar_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="servicio_semanal_{year}_{month}.pdf"'
        },
    )
