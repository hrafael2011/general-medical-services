from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.core.config import settings
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.schemas.calendars import (
    ApproveCalendarRequest,
    AssignDoctorRequest,
    CalendarAssignmentRead,
    CalendarGridResponse,
    CalendarRead,
    CalendarVersionRead,
    CreateCalendarRequest,
    DaySlot,
    ReplaceAssignmentRequest,
    UnresolvedGapRead,
)
from backend.app.schemas.generation import GenerationResponse, GenerationSlotResult

router = APIRouter(prefix="/calendars", tags=["calendars"])


# ---------------------------------------------------------------------------
# Error code → HTTP status mapping
# ---------------------------------------------------------------------------

_ERROR_STATUS: dict[str, int] = {
    "calendar_not_found": status.HTTP_404_NOT_FOUND,
    "version_not_found": status.HTTP_404_NOT_FOUND,
    "assignment_not_found": status.HTTP_404_NOT_FOUND,
    "doctor_not_found": status.HTTP_404_NOT_FOUND,
    "calendar_already_exists": status.HTTP_409_CONFLICT,
    "hard_block": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "soft_warning": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "version_is_approved": status.HTTP_409_CONFLICT,
    "calendar_already_approved": status.HTTP_409_CONFLICT,
    "invalid_status_transition": status.HTTP_409_CONFLICT,
}


def _http_exc(exc: CalendarServiceError) -> HTTPException:
    http_status = _ERROR_STATUS.get(exc.code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    return HTTPException(
        status_code=http_status,
        detail={"code": exc.code, "message": exc.message},
    )


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------

def get_calendar_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarService:
    from backend.app.application.audit.service import AuditService
    from backend.app.application.notifications.providers import FakeProvider, TwilioProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.triggers import NotificationTriggers
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository

    provider = TwilioProvider() if settings.twilio_account_sid else FakeProvider()
    triggers = NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(session),
            provider=provider,
        ),
        doctor_repo=DoctorRepository(session),
    )

    return CalendarService(
        CalendarRepository(session),
        audit=AuditService(AuditRepository(session)),
        triggers=triggers,
    )


def get_generation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> GenerationService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository

    return GenerationService(
        CalendarRepository(session),
        DoctorRepository(session),
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
    )


def get_assignment_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AssignmentService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository

    return AssignmentService(
        CalendarRepository(session),
        DoctorRepository(session),
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
    )


# ---------------------------------------------------------------------------
# Calendar endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CalendarRead])
def list_calendars(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> list[CalendarRead]:
    calendars = service.list_calendars()
    return [CalendarRead.model_validate(c) for c in calendars]


@router.post("", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(
    payload: CreateCalendarRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarRead:
    try:
        calendar = service.create_calendar(
            actor_id=current_user.id,
            month=payload.month,
            year=payload.year,
            notes=getattr(payload, "notes", None),
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarRead.model_validate(calendar)


@router.get("/{calendar_id}", response_model=CalendarRead)
def get_calendar(
    calendar_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarRead:
    try:
        calendar = service.get_calendar(calendar_id)
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    return CalendarRead.model_validate(calendar)


@router.get("/{calendar_id}/grid", response_model=CalendarGridResponse)
def get_calendar_grid(
    calendar_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarGridResponse:
    try:
        calendar = service.get_calendar(calendar_id)
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc

    repo = CalendarRepository(session)

    version = repo.get_latest_version(calendar_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "version_not_found", "message": f"No versions found for calendar {calendar_id}."},
        )

    assignments = repo.list_assignments(version.id)
    gaps = repo.list_gaps(version.id)

    slots: list[DaySlot] = [
        DaySlot(
            service_date=a.service_date,
            service_area_id=a.service_area_id,
            assignment=CalendarAssignmentRead.model_validate(a),
        )
        for a in assignments
    ]

    return CalendarGridResponse(
        calendar=CalendarRead.model_validate(calendar),
        version=CalendarVersionRead.model_validate(version),
        slots=slots,
        gaps=[UnresolvedGapRead.model_validate(g).model_dump() for g in gaps],
    )


@router.post("/{calendar_id}/approve", response_model=CalendarVersionRead)
def approve_calendar(
    calendar_id: str,
    payload: ApproveCalendarRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarVersionRead:
    # Approve the latest version of this calendar.
    repo = CalendarRepository(session)
    version = repo.get_latest_version(calendar_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "version_not_found", "message": f"No versions found for calendar {calendar_id}."},
        )
    try:
        approved_version = service.approve_version(
            actor_id=current_user.id,
            calendar_id=calendar_id,
            version_number=version.version_number,
            notes=payload.reason,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarVersionRead.model_validate(approved_version)


@router.post("/{calendar_id}/new-version", response_model=CalendarVersionRead, status_code=status.HTTP_201_CREATED)
def new_version(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
    reason: str | None = None,
) -> CalendarVersionRead:
    try:
        new_ver = service.new_version_after_approval(
            actor_id=current_user.id,
            calendar_id=calendar_id,
            reason=reason,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarVersionRead.model_validate(new_ver)


@router.post("/{calendar_id}/generate", response_model=GenerationResponse, status_code=status.HTTP_200_OK)
def generate_calendar(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[GenerationService, Depends(get_generation_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GenerationResponse:
    try:
        summary = service.generate(actor_id=current_user.id, calendar_id=calendar_id)
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return GenerationResponse(
        version_id=summary.version_id,
        calendar_id=summary.calendar_id,
        month=summary.month,
        year=summary.year,
        total_slots=summary.total_slots,
        assigned_count=summary.assigned_count,
        gap_count=summary.gap_count,
        slots=[
            GenerationSlotResult(
                service_date=r.slot.date,
                service_area_id=r.slot.service_area_id,
                assigned_doctor_id=r.assigned_doctor_id,
                warnings=r.score.warnings if r.score else [],
                score=r.score.score if r.score else None,
            )
            for r in summary.slot_results
        ],
    )


# ---------------------------------------------------------------------------
# Assignment endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{calendar_id}/versions/{version_id}/assignments",
    response_model=CalendarAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_doctor(
    calendar_id: str,
    version_id: str,
    payload: AssignDoctorRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarAssignmentRead:
    try:
        assignment = service.assign_doctor(
            actor_id=current_user.id,
            version_id=version_id,
            doctor_id=payload.doctor_id,
            date=payload.service_date,
            service_area_id=payload.service_area_id,
            override_justification=payload.override_justification,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarAssignmentRead.model_validate(assignment)


@router.delete(
    "/{calendar_id}/versions/{version_id}/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_assignment(
    calendar_id: str,
    version_id: str,
    assignment_id: str,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.remove_assignment(
            actor_id=current_user.id,
            assignment_id=assignment_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()


@router.patch(
    "/{calendar_id}/versions/{version_id}/assignments/{assignment_id}",
    response_model=CalendarAssignmentRead,
)
def replace_assignment(
    calendar_id: str,
    version_id: str,
    assignment_id: str,
    payload: ReplaceAssignmentRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarAssignmentRead:
    try:
        assignment = service.replace_assignment(
            actor_id=current_user.id,
            assignment_id=assignment_id,
            new_doctor_id=payload.doctor_id,
            override_justification=payload.override_justification,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarAssignmentRead.model_validate(assignment)
