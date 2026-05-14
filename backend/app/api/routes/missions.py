from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.missions.candidate_service import MissionCandidateService
from backend.app.application.missions.errors import MissionServiceError
from backend.app.application.missions.ranking_service import MissionRankingService
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.schemas.missions import (
    ConfirmMissionRequest,
    CreateMissionRequest,
    MissionAssignmentRead,
    MissionCandidateDateRankingEntryRead,
    MissionCandidateDateRankingResponse,
    MissionCandidateRankingEntryRead,
    MissionCandidateRankingRead,
    MissionCandidateRequest,
    MissionCandidateResponse,
    MissionParticipantRead,
    MissionReplacementAlertSummary,
    UpdateMissionRequest,
)

router = APIRouter(prefix="/missions", tags=["missions"])


# ---------------------------------------------------------------------------
# Inline request schema
# ---------------------------------------------------------------------------

class GenerateRankingRequest(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    calendar_version_id: str | None = None


# ---------------------------------------------------------------------------
# Error code → HTTP status mapping
# ---------------------------------------------------------------------------

_ERROR_STATUS: dict[str, int] = {
    "mission_not_found": status.HTTP_404_NOT_FOUND,
    "ranking_not_found": status.HTTP_404_NOT_FOUND,
    "approved_calendar_required": status.HTTP_409_CONFLICT,
    "already_confirmed": status.HTTP_409_CONFLICT,
    "candidate_not_available": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _http_exc(exc: MissionServiceError) -> HTTPException:
    http_status = _ERROR_STATUS.get(exc.code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    return HTTPException(
        status_code=http_status,
        detail={"code": exc.code, "message": exc.message},
    )


# ---------------------------------------------------------------------------
# Dependency factories
# ---------------------------------------------------------------------------

def get_ranking_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionRankingService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository

    return MissionRankingService(
        MissionRepository(session),
        DoctorRepository(session),
        CalendarRepository(session),
        CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
    )


def get_candidate_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionCandidateService:
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.application.audit.service import AuditService
    from backend.app.application.confirmations.service import ConfirmationRequestService
    from backend.app.application.notifications.providers import FakeProvider, TwilioProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.triggers import NotificationTriggers
    from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository

    provider = TwilioProvider() if settings.twilio_account_sid else FakeProvider()
    triggers = NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(session),
            provider=provider,
        ),
        doctor_repo=DoctorRepository(session),
        confirmation_service=ConfirmationRequestService(
            ConfirmationRequestRepository(session),
        ),
        confirmation_due_hours=settings.confirmation_overdue_hours,
    )

    return MissionCandidateService(
        MissionRepository(session),
        CalendarRepository(session),
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
        triggers=triggers,
        action_alerts=ActionAlertService(ActionAlertRepository(session)),
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _to_ranking_read(
    ranking, repo: MissionRepository
) -> MissionCandidateRankingRead:
    data = MissionCandidateRankingRead.model_validate(ranking)
    data.entries = _ranking_entries_with_doctor_names(repo, repo.list_ranking_entries(ranking.id))
    return data


def _to_mission_read(
    mission, repo: MissionRepository
) -> MissionAssignmentRead:
    data = MissionAssignmentRead.model_validate(mission)
    data.participants = _participants_with_doctor_names(repo, repo.list_participants(mission.id))
    _apply_mission_replacement_warnings(data, mission.mission_date, mission.status, repo)
    return data


def _doctor_rows(repo: MissionRepository, doctor_ids: list[str]):
    if not doctor_ids:
        return []
    from backend.app.infrastructure.db.models.doctors import DoctorModel

    return repo.session.query(DoctorModel).filter(DoctorModel.id.in_(doctor_ids)).all()


def _doctor_names(repo: MissionRepository, doctor_ids: list[str]) -> dict[str, str]:
    return {doctor.id: doctor.name for doctor in _doctor_rows(repo, doctor_ids)}


def _doctor_replacement_reasons(repo: MissionRepository, doctor_ids: list[str]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for doctor in _doctor_rows(repo, doctor_ids):
        if not doctor.active:
            reasons[doctor.id] = "Médico inactivo en el sistema."
        elif not doctor.service_active:
            reasons[doctor.id] = "Médico inactivo para servicio."
        elif not doctor.participa_misiones:
            reasons[doctor.id] = "Médico no participa en misiones."
    return reasons


def _ranking_entries_with_doctor_names(
    repo: MissionRepository,
    entries,
) -> list[MissionCandidateRankingEntryRead]:
    names = _doctor_names(repo, [entry.doctor_id for entry in entries])
    data = []
    for entry in entries:
        row = MissionCandidateRankingEntryRead.model_validate(entry)
        row.doctor_name = names.get(entry.doctor_id)
        data.append(row)
    return data


def _participants_with_doctor_names(
    repo: MissionRepository,
    participants,
) -> list[MissionParticipantRead]:
    names = _doctor_names(repo, [participant.doctor_id for participant in participants])
    data = []
    for participant in participants:
        row = MissionParticipantRead.model_validate(participant)
        row.doctor_name = names.get(participant.doctor_id)
        data.append(row)
    return data


def _apply_mission_replacement_warnings(
    mission_read: MissionAssignmentRead,
    mission_date: date,
    mission_status: str,
    repo: MissionRepository,
) -> None:
    if mission_status != "confirmed" or mission_date < date.today():
        return

    reasons = _doctor_replacement_reasons(
        repo,
        [participant.doctor_id for participant in mission_read.participants],
    )
    for participant in mission_read.participants:
        reason = reasons.get(participant.doctor_id)
        if reason:
            participant.requires_replacement = True
            participant.replacement_reason = reason

    mission_read.replacement_warning_count = sum(
        1 for participant in mission_read.participants if participant.requires_replacement
    )
    mission_read.has_replacement_warnings = mission_read.replacement_warning_count > 0


def _date_ranking_entries_with_doctor_names(
    repo: MissionRepository,
    items: list[dict],
) -> list[MissionCandidateDateRankingEntryRead]:
    entries = [item["entry"] for item in items]
    names = _doctor_names(repo, [entry.doctor_id for entry in entries])
    data: list[MissionCandidateDateRankingEntryRead] = []
    for item in items:
        entry = item["entry"]
        data.append(
            MissionCandidateDateRankingEntryRead(
                id=entry.id,
                doctor_id=entry.doctor_id,
                doctor_name=names.get(entry.doctor_id),
                ranking_position=entry.ranking_position,
                adjusted_position=item["adjusted_position"],
                recommendation_status=item["recommendation_status"],
                selectable=item["selectable"],
                total_load_score=entry.total_load_score,
                monthly_service_load=entry.monthly_service_load,
                recent_service_load=entry.recent_service_load,
                monthly_mission_load=entry.monthly_mission_load,
                eligible=entry.eligible,
                reasons=item["reasons"],
                warnings=item["warnings"],
            )
        )
    return data


def _approved_version_or_409(
    session: Session,
    *,
    year: int,
    month: int,
):
    version = CalendarRepository(session).get_approved_version_by_period(year, month)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "approved_calendar_required",
                "message": (
                    f"No hay calendario aprobado para {year}/{month:02d}. "
                    "Apruebe el calendario antes de consultar el ranking."
                ),
            },
        )
    return version


# ---------------------------------------------------------------------------
# Ranking endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/rankings/generate",
    response_model=MissionCandidateRankingRead,
    status_code=status.HTTP_200_OK,
)
def generate_ranking(
    payload: GenerateRankingRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionRankingService, Depends(get_ranking_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionCandidateRankingRead:
    ranking = service.generate_ranking(
        actor_id=current_user.id,
        year=payload.year,
        month=payload.month,
        calendar_version_id=payload.calendar_version_id,
    )
    session.commit()
    repo = MissionRepository(session)
    return _to_ranking_read(ranking, repo)


@router.get(
    "/rankings/{year}/{month}",
    response_model=MissionCandidateRankingRead,
)
def get_ranking(
    year: int,
    month: int,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionRankingService, Depends(get_ranking_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionCandidateRankingRead:
    approved_version = _approved_version_or_409(session, year=year, month=month)
    ranking = service.get_ranking(
        year=year,
        month=month,
        calendar_version_id=approved_version.id,
    )
    if ranking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ranking_not_found",
                "message": f"No ranking found for approved calendar {year}/{month:02d}.",
            },
        )
    repo = MissionRepository(session)
    return _to_ranking_read(ranking, repo)


# ---------------------------------------------------------------------------
# Candidate recommendation endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/candidates",
    response_model=MissionCandidateResponse,
)
def recommend_candidates(
    payload: MissionCandidateRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
) -> MissionCandidateResponse:
    try:
        result = service.recommend_candidates(
            year=payload.mission_date.year,
            month=payload.mission_date.month,
            mission_date=payload.mission_date,
            participant_count=payload.participant_count,
            include_alternates=payload.include_alternates,
        )
    except MissionServiceError as exc:
        raise _http_exc(exc) from exc

    return MissionCandidateResponse(
        mission_date=payload.mission_date,
        participant_count=payload.participant_count,
        primary=_ranking_entries_with_doctor_names(service.mission_repo, result["primary"]),
        alternates=_ranking_entries_with_doctor_names(service.mission_repo, result["alternates"]),
    )


@router.post(
    "/candidates/ranked",
    response_model=MissionCandidateDateRankingResponse,
)
def rank_candidates_for_date(
    payload: MissionCandidateRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
) -> MissionCandidateDateRankingResponse:
    try:
        entries = service.rank_candidates_for_date(
            year=payload.mission_date.year,
            month=payload.mission_date.month,
            mission_date=payload.mission_date,
        )
    except MissionServiceError as exc:
        raise _http_exc(exc) from exc

    return MissionCandidateDateRankingResponse(
        mission_date=payload.mission_date,
        year=payload.mission_date.year,
        month=payload.mission_date.month,
        entries=_date_ranking_entries_with_doctor_names(service.mission_repo, entries),
    )


# ---------------------------------------------------------------------------
# Mission assignment endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=MissionAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_mission(
    payload: CreateMissionRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionAssignmentRead:
    mission = service.create_mission(
        actor_id=current_user.id,
        mission_date=payload.mission_date,
        participant_count=payload.participant_count,
        location=payload.location,
        description=payload.description,
    )
    session.commit()
    repo = MissionRepository(session)
    return _to_mission_read(mission, repo)


@router.get(
    "",
    response_model=list[MissionAssignmentRead],
)
def list_missions(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[MissionAssignmentRead]:
    repo = MissionRepository(session)
    missions = repo.list_missions()
    # Bulk load participants to avoid N+1
    participants_by_mission = repo.list_participants_bulk([m.id for m in missions])
    items = []
    for m in missions:
        data = MissionAssignmentRead.model_validate(m)
        data.participants = _participants_with_doctor_names(
            repo,
            participants_by_mission.get(m.id, []),
        )
        _apply_mission_replacement_warnings(data, m.mission_date, m.status, repo)
        items.append(data)
    return items


@router.get(
    "/replacement-alerts/summary",
    response_model=MissionReplacementAlertSummary,
)
def get_replacement_alert_summary(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionReplacementAlertSummary:
    repo = MissionRepository(session)
    missions = repo.list_missions()
    participants_by_mission = repo.list_participants_bulk([m.id for m in missions])
    mission_count = 0
    participant_count = 0
    for mission in missions:
        if mission.status != "confirmed" or mission.mission_date < date.today():
            continue
        participants = participants_by_mission.get(mission.id, [])
        reasons = _doctor_replacement_reasons(
            repo,
            [participant.doctor_id for participant in participants],
        )
        count = sum(1 for participant in participants if participant.doctor_id in reasons)
        if count:
            mission_count += 1
            participant_count += count
    return MissionReplacementAlertSummary(
        mission_count=mission_count,
        participant_count=participant_count,
    )


@router.get(
    "/{mission_id}",
    response_model=MissionAssignmentRead,
)
def get_mission(
    mission_id: str,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionAssignmentRead:
    repo = MissionRepository(session)
    mission = repo.get_mission_by_id(mission_id)
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "mission_not_found",
                "message": f"Mission with id {mission_id} not found.",
            },
        )
    return _to_mission_read(mission, repo)


@router.patch(
    "/{mission_id}",
    response_model=MissionAssignmentRead,
)
def update_mission(
    mission_id: str,
    payload: UpdateMissionRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionAssignmentRead:
    try:
        mission = service.update_mission(
            actor_id=current_user.id,
            mission_id=mission_id,
            updates=payload.model_dump(exclude_unset=True),
        )
    except MissionServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    repo = MissionRepository(session)
    return _to_mission_read(mission, repo)


@router.delete(
    "/{mission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_mission(
    mission_id: str,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.delete_mission(actor_id=current_user.id, mission_id=mission_id)
    except MissionServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    return None


@router.post(
    "/{mission_id}/confirm",
    response_model=MissionAssignmentRead,
)
def confirm_mission(
    mission_id: str,
    payload: ConfirmMissionRequest,
    current_user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[MissionCandidateService, Depends(get_candidate_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> MissionAssignmentRead:
    try:
        mission = service.confirm_mission(
            actor_id=current_user.id,
            mission_id=mission_id,
            doctor_ids=payload.doctor_ids,
        )
    except MissionServiceError as exc:
        raise _http_exc(exc) from exc
    session.commit()
    repo = MissionRepository(session)
    return _to_mission_read(mission, repo)
