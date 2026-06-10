from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission, require_ready_user
from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.schemas.calendars import (
    ApproveCalendarRequest,
    ApproveWeekRequest,
    AssignDoctorRequest,
    CalendarAssignmentRead,
    CalendarGridResponse,
    CalendarRead,
    CalendarVersionRead,
    CreateCalendarRequest,
    DaySlot,
    DoctorAssignmentCountRead,
    EligibleDoctorRead,
    EligibleDoctorsResponse,
    EvaluationRequest,
    EvaluationResponse,
    HardBlockItem,
    ReplaceAssignmentRequest,
    UnresolvedGapRead,
    WarningItem,
    WeekRead,
)
from backend.app.schemas.generation import GenerationResponse, GenerationSlotResult
from backend.app.infrastructure.db.models.doctors import DoctorModel

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
    "invalid_generation_mode": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "generation_configuration_incomplete": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "week_not_found": status.HTTP_404_NOT_FOUND,
    "week_already_approved": status.HTTP_409_CONFLICT,
    "week_not_approved": status.HTTP_409_CONFLICT,
    "week_empty": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "week_locked": status.HTTP_409_CONFLICT,
    "calendar_not_deleted": status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    from backend.app.application.confirmations.service import ConfirmationRequestService
    from backend.app.application.missions.ranking_service import MissionRankingService
    from backend.app.application.notifications.providers import FakeProvider, MetaCloudAPIProvider, TelegramNotificationProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.triggers import NotificationTriggers
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository

    audit = AuditService(AuditRepository(session))
    calendar_repo = CalendarRepository(session)
    doctor_repo = DoctorRepository(session)
    if settings.telegram_notification_bot_token:
        provider = TelegramNotificationProvider()
    elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
        provider = MetaCloudAPIProvider()
    else:
        provider = FakeProvider()
    triggers = NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(session),
            provider=provider,
        ),
        doctor_repo=doctor_repo,
        confirmation_service=ConfirmationRequestService(
            ConfirmationRequestRepository(session),
        ),
        confirmation_due_hours=settings.confirmation_overdue_hours,
    )
    mission_ranking_service = MissionRankingService(
        MissionRepository(session),
        doctor_repo,
        calendar_repo,
        CatalogRepository(session),
        audit=audit,
    )

    return CalendarService(
        calendar_repo,
        audit=audit,
        triggers=triggers,
        mission_ranking_service=mission_ranking_service,
    )


def get_generation_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> GenerationService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository

    from backend.app.application.missions.ranking_service import MissionRankingService

    return GenerationService(
        CalendarRepository(session),
        DoctorRepository(session),
        AvailabilityRepository(session),
        MissionRepository(session),
        CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
        mission_ranking_service=MissionRankingService(
            MissionRepository(session),
            DoctorRepository(session),
            CalendarRepository(session),
            CatalogRepository(session),
            audit=AuditService(AuditRepository(session)),
        ),
    )


def get_assignment_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> AssignmentService:
    from backend.app.application.audit.service import AuditService
    from backend.app.application.confirmations.service import ConfirmationRequestService
    from backend.app.application.notifications.providers import FakeProvider, MetaCloudAPIProvider, TelegramNotificationProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.triggers import NotificationTriggers
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
    from backend.app.application.missions.ranking_service import MissionRankingService
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository

    doctor_repo = DoctorRepository(session)
    if settings.telegram_notification_bot_token:
        provider = TelegramNotificationProvider()
    elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
        provider = MetaCloudAPIProvider()
    else:
        provider = FakeProvider()
    triggers = NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(session),
            provider=provider,
        ),
        doctor_repo=doctor_repo,
        confirmation_service=ConfirmationRequestService(
            ConfirmationRequestRepository(session),
        ),
        confirmation_due_hours=settings.confirmation_overdue_hours,
    )

    mission_ranking_service = MissionRankingService(
        MissionRepository(session),
        doctor_repo,
        CalendarRepository(session),
        CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
    )

    return AssignmentService(
        CalendarRepository(session),
        doctor_repo,
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
        triggers=triggers,
        mission_ranking_service=mission_ranking_service,
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
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarRead:
    try:
        calendar = service.create_calendar(
            actor_id=current_user.id,
            month=payload.month,
            year=payload.year,
            notes=getattr(payload, "notes", None),
            generation_mode=payload.generation_mode,
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


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_calendar(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.soft_delete_calendar(
            actor_id=current_user.id,
            calendar_id=calendar_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()


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
            detail={
                "code": "version_not_found",
                "message": f"No versions found for calendar {calendar_id}.",
            },
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
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarVersionRead:
    # Approve the latest version of this calendar.
    repo = CalendarRepository(session)
    version = repo.get_latest_version(calendar_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "version_not_found",
                "message": f"No versions found for calendar {calendar_id}.",
            },
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


@router.post(
    "/{calendar_id}/new-version",
    response_model=CalendarVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def new_version(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
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


@router.post("/{calendar_id}/unlock", response_model=CalendarVersionRead)
def unlock_calendar(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarVersionRead:
    try:
        version = service.unlock_calendar(
            actor_id=current_user.id,
            calendar_id=calendar_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarVersionRead.model_validate(version)


@router.get(
    "/{calendar_id}/eligible-doctors",
    response_model=EligibleDoctorsResponse,
)
def get_eligible_doctors(
    calendar_id: str,
    date: date,
    area_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> EligibleDoctorsResponse:
    repo = CalendarRepository(session)
    version = repo.get_latest_version(calendar_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "version_not_found",
                "message": f"No versions found for calendar {calendar_id}.",
            },
        )
    try:
        doctors = service.get_eligible_doctors_for_slot(
            version_id=version.id,
            target_date=date,
            service_area_id=area_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    return EligibleDoctorsResponse(
        doctors=[
            EligibleDoctorRead(
                id=d.id,
                full_name=d.name,
                specialty=getattr(d, "specialty", None),
                rank_name=getattr(d, "rank_name", None),
            )
            for d in doctors
        ]
    )


@router.post(
    "/{calendar_id}/evaluate",
    response_model=EvaluationResponse,
)
def evaluate_slot(
    calendar_id: str,
    payload: EvaluationRequest,
    _current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> EvaluationResponse:
    repo = CalendarRepository(session)
    version = repo.get_latest_version(calendar_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "version_not_found",
                "message": f"No versions found for calendar {calendar_id}.",
            },
        )
    try:
        result = service.evaluate_slot(
            version_id=version.id,
            doctor_id=payload.doctor_id,
            target_date=payload.service_date,
            service_area_id=payload.service_area_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    return EvaluationResponse(
        hard_blocks=[HardBlockItem(**b) for b in result["hard_blocks"]],
        warnings=[WarningItem(**w) for w in result["warnings"]],
    )


@router.post(
    "/{calendar_id}/generate",
    response_model=GenerationResponse,
    status_code=status.HTTP_200_OK,
)
def generate_calendar(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[GenerationService, Depends(get_generation_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GenerationResponse:
    try:
        summary = service.generate(
            actor_id=current_user.id,
            calendar_id=calendar_id,
            generation_mode="assisted_auto",
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    calendar = service.calendar_repo.get_calendar_by_id(calendar_id)
    return GenerationResponse(
        version_id=summary.version_id,
        calendar_id=summary.calendar_id,
        month=summary.month,
        year=summary.year,
        calendar_status=calendar.status if calendar else "draft",
        generation_mode=calendar.generation_mode if calendar else "assisted_auto",
        review_required=True,
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


@router.post(
    "/{calendar_id}/fill-gaps",
    status_code=status.HTTP_200_OK,
)
def fill_gaps(
    calendar_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[GenerationService, Depends(get_generation_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Fill only unresolved gaps without touching existing assignments."""
    try:
        result = service.fill_gaps(
            actor_id=current_user.id,
            calendar_id=calendar_id,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return result


# ---------------------------------------------------------------------------
# Week endpoints
# ---------------------------------------------------------------------------

@router.get("/{calendar_id}/weeks", response_model=list[WeekRead])
def list_weeks(
    calendar_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[WeekRead]:
    """List all weeks for a calendar with status and assignment count."""
    repo = CalendarRepository(session)
    weeks = repo.list_weeks(calendar_id)
    result: list[WeekRead] = []
    all_assignments = repo.list_assignments(weeks[0].calendar_version_id) if weeks else []
    for w in weeks:
        week_assignments = [
            a for a in all_assignments
            if w.start_date <= a.service_date <= w.end_date
        ]
        counts_by_doctor: dict[str, int] = {}
        for assignment in week_assignments:
            counts_by_doctor[assignment.doctor_id] = (
                counts_by_doctor.get(assignment.doctor_id, 0) + 1
            )
        doctor_counts: list[DoctorAssignmentCountRead] = []
        for doctor_id, count in counts_by_doctor.items():
            doctor = session.get(DoctorModel, doctor_id)
            doctor_counts.append(DoctorAssignmentCountRead(
                doctor_id=doctor_id,
                doctor_name=doctor.name if doctor is not None else doctor_id,
                count=count,
            ))
        result.append(WeekRead(
            id=w.id,
            week_number=w.week_number,
            label=w.label,
            start_date=w.start_date.isoformat(),
            end_date=w.end_date.isoformat(),
            status=w.status,
            assignment_count=len(week_assignments),
            doctor_assignment_counts=doctor_counts,
            approved_by=w.approved_by,
            approved_at=w.approved_at.isoformat() if w.approved_at else None,
        ))
    return result


@router.post("/{calendar_id}/weeks/{week_id}/approve", response_model=WeekRead)
def approve_week(
    calendar_id: str,
    week_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
    payload: ApproveWeekRequest | None = None,
) -> WeekRead:
    """Approve a single week. Notifications are sent to its assigned doctors."""
    try:
        week = service.approve_week(
            actor_id=current_user.id,
            week_id=week_id,
            notes=payload.notes if payload else None,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return WeekRead(
        id=week.id,
        week_number=week.week_number,
        label=week.label,
        start_date=week.start_date.isoformat(),
        end_date=week.end_date.isoformat(),
        status=week.status,
        assignment_count=0,
        approved_by=week.approved_by,
        approved_at=week.approved_at.isoformat() if week.approved_at else None,
    )


@router.post("/{calendar_id}/weeks/{week_id}/unlock", response_model=WeekRead)
def unlock_week(
    calendar_id: str,
    week_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    session: Annotated[Session, Depends(get_db_session)],
    payload: ApproveWeekRequest | None = None,
) -> WeekRead:
    """Revert a week to draft for editing."""
    try:
        week = service.unlock_week(
            actor_id=current_user.id,
            week_id=week_id,
            notes=payload.notes if payload else None,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return WeekRead(
        id=week.id,
        week_number=week.week_number,
        label=week.label,
        start_date=week.start_date.isoformat(),
        end_date=week.end_date.isoformat(),
        status=week.status,
        assignment_count=0,
        approved_by=None,
        approved_at=None,
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
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
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
            force_warnings=payload.force_warnings,
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
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
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
    current_user: Annotated[UserModel, Depends(require_permission("manage_calendars"))],
    service: Annotated[AssignmentService, Depends(get_assignment_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarAssignmentRead:
    try:
        assignment = service.replace_assignment(
            actor_id=current_user.id,
            assignment_id=assignment_id,
            new_doctor_id=payload.doctor_id,
            override_justification=payload.override_justification,
            force_warnings=payload.force_warnings,
        )
    except CalendarServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return CalendarAssignmentRead.model_validate(assignment)
