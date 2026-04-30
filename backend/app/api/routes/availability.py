from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.availability.errors import AvailabilityError
from backend.app.application.availability.service import AvailabilityService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.schemas.availability import (
    AddRestrictionRequest,
    AvailabilityRead,
    PendingAvailabilityItem,
    PendingAvailabilityResponse,
    RestrictionRead,
    SetMonthlyAvailabilityRequest,
    SetWeeklyAvailabilityRequest,
)

router = APIRouter(prefix="/availability", tags=["availability"])


def get_availability_service(session: Annotated[Session, Depends(get_db_session)]) -> AvailabilityService:
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.application.audit.service import AuditService
    return AvailabilityService(
        availability_repo=AvailabilityRepository(session),
        doctor_repo=DoctorRepository(session),
        audit=AuditService(AuditRepository(session)),
    )


def _availability_error_to_http(exc: AvailabilityError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND
        if exc.code in ("doctor_not_found", "restriction_not_found")
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message})


@router.get("/doctors/{doctor_id}", response_model=list[AvailabilityRead])
def list_availability(
    doctor_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[AvailabilityRead]:
    repo = AvailabilityRepository(session)
    records = repo.list_availability_for_doctor(doctor_id)
    return [AvailabilityRead.model_validate(r) for r in records]


@router.post("/doctors/{doctor_id}/weekly", response_model=AvailabilityRead, status_code=201)
def set_weekly_availability(
    doctor_id: str,
    payload: SetWeeklyAvailabilityRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AvailabilityRead:
    try:
        record = service.set_weekly_availability(
            doctor_id,
            days_of_week=payload.days_of_week,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            actor_id=current_user.id,
        )
    except AvailabilityError as exc:
        raise _availability_error_to_http(exc) from exc
    session.commit()
    return AvailabilityRead.model_validate(record)


@router.post("/doctors/{doctor_id}/monthly", response_model=AvailabilityRead, status_code=201)
def set_monthly_availability(
    doctor_id: str,
    payload: SetMonthlyAvailabilityRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> AvailabilityRead:
    try:
        record = service.set_monthly_availability(
            doctor_id,
            year=payload.year,
            month=payload.month,
            available_dates=payload.available_dates,
            actor_id=current_user.id,
        )
    except AvailabilityError as exc:
        raise _availability_error_to_http(exc) from exc
    session.commit()
    return AvailabilityRead.model_validate(record)


@router.get("/doctors/{doctor_id}/restrictions", response_model=list[RestrictionRead])
def list_restrictions(
    doctor_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RestrictionRead]:
    repo = AvailabilityRepository(session)
    records = repo.list_restrictions_for_doctor(doctor_id)
    return [RestrictionRead.model_validate(r) for r in records]


@router.post("/doctors/{doctor_id}/restrictions", response_model=RestrictionRead, status_code=201)
def add_restriction(
    doctor_id: str,
    payload: AddRestrictionRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RestrictionRead:
    try:
        record = service.add_restriction(
            doctor_id,
            restriction_type=payload.restriction_type,
            severity=payload.severity,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            description=payload.description,
            reason_id=payload.reason_id,
            actor_id=current_user.id,
        )
    except AvailabilityError as exc:
        raise _availability_error_to_http(exc) from exc
    session.commit()
    return RestrictionRead.model_validate(record)


@router.post("/restrictions/{restriction_id}/lift", response_model=RestrictionRead)
def lift_restriction(
    restriction_id: str,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RestrictionRead:
    try:
        record = service.lift_restriction(restriction_id, actor_id=current_user.id)
    except AvailabilityError as exc:
        raise _availability_error_to_http(exc) from exc
    session.commit()
    return RestrictionRead.model_validate(record)


@router.get("/pending", response_model=PendingAvailabilityResponse)
def get_pending_availability(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    year: int = Query(ge=2020, le=2100),
    month: int = Query(ge=1, le=12),
) -> PendingAvailabilityResponse:
    doctor_repo = DoctorRepository(session)
    availability_repo = AvailabilityRepository(session)
    service = AvailabilityService(
        availability_repo=availability_repo,
        doctor_repo=doctor_repo,
    )

    monthly_doctors = [
        d for d in doctor_repo.list_service_active()
        if d.availability_mode == "monthly"
    ]

    pending = [
        PendingAvailabilityItem(
            doctor_id=doctor.id,
            doctor_name=doctor.name,
            availability_mode=doctor.availability_mode,
        )
        for doctor in monthly_doctors
        if not service.has_submitted_monthly_availability(doctor.id, year=year, month=month)
    ]

    return PendingAvailabilityResponse(year=year, month=month, pending=pending, total=len(pending))
