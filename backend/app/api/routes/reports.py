import io
from datetime import date
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


@router.get("/coverage", response_model=None)
def get_coverage(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year_start: int = Query(..., ge=2000, le=2100),
    month_start: int = Query(..., ge=1, le=12),
    year_end: int = Query(..., ge=2000, le=2100),
    month_end: int = Query(..., ge=1, le=12),
    area: str | None = Query(default=None),
    rank_id: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    format: str | None = Query(default=None),
) -> StreamingResponse | dict:
    data = service.generate_coverage(
        year_start=year_start, month_start=month_start,
        year_end=year_end, month_end=month_end,
        area=area, rank_id=rank_id, sex=sex, department_id=department_id,
    )
    if format == "pdf":
        from backend.app.application.reports.pdf_templates import generate_coverage_pdf
        pdf_bytes = generate_coverage_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="cobertura_{year_start}_{month_start}.pdf"'},
        )
    return data


@router.get("/workload", response_model=None)
def get_workload(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    area: str | None = Query(default=None),
    rank_id: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    group_by: str = Query(default="none"),
    order_by: str = Query(default="total_desc"),
    format: str | None = Query(default=None),
) -> StreamingResponse | dict:
    data = service.generate_workload(
        year=year, month=month,
        area=area, rank_id=rank_id, sex=sex, department_id=department_id,
        group_by=group_by, order_by=order_by,
    )
    if format == "pdf":
        from backend.app.application.reports.pdf_templates import generate_workload_pdf
        pdf_bytes = generate_workload_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="carga_trabajo_{year}_{month}.pdf"'},
        )
    return data


@router.get("/doctor-dossier/{doctor_id}", response_model=None)
def get_doctor_dossier(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
    doctor_id: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    format: str | None = Query(default=None),
) -> StreamingResponse | dict:
    try:
        data = service.generate_doctor_dossier(
            doctor_id=doctor_id, date_from=date_from, date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if format == "pdf":
        from backend.app.application.reports.pdf_templates import generate_dossier_pdf
        pdf_bytes = generate_dossier_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="ficha_{doctor_id[:8]}.pdf"'},
        )
    return data


@router.get("/calendar/{calendar_id}/weeks/{week_id}/pdf")
def export_weekly_list_pdf(
    calendar_id: str,
    week_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> StreamingResponse:
    """Export a weekly list as PDF with institutional branding."""
    week = service.calendar_repo.get_week_by_id(week_id)
    if week is None:
        raise HTTPException(status_code=404, detail=f"Week {week_id} not found")
    try:
        pdf_bytes = service.build_weekly_schedule(
            year=week.start_date.year,
            month=week.start_date.month,
            week_id=week_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=lista-semanal-{week_id[:8]}.pdf"
        },
    )


@router.get("/calendar/{calendar_id}/full-pdf")
def export_full_calendar_pdf(
    calendar_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> StreamingResponse:
    """Export the full calendar as a single-page PDF grid."""
    try:
        grid_data = service.build_full_calendar_by_id(calendar_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    from backend.app.application.reports.pdf_templates import generate_full_calendar_pdf
    pdf_bytes = generate_full_calendar_pdf(grid_data)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=calendario-completo-{calendar_id[:8]}.pdf"
        },
    )
