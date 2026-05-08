from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.missions.candidate_service import MissionCandidateService
from backend.app.core.config import settings
from backend.app.application.missions.errors import MissionServiceError
from backend.app.application.missions.ranking_service import MissionRankingService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.schemas.missions import (
    ConfirmMissionRequest,
    CreateMissionRequest,
    MissionAssignmentRead,
    MissionCandidateRankingEntryRead,
    MissionCandidateRankingRead,
    MissionCandidateRequest,
    MissionCandidateResponse,
    MissionParticipantRead,
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
    "already_confirmed": status.HTTP_409_CONFLICT,
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
    from backend.app.application.audit.service import AuditService
    from backend.app.application.notifications.providers import FakeProvider, TwilioProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.triggers import NotificationTriggers
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
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

    return MissionCandidateService(
        MissionRepository(session),
        CalendarRepository(session),
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
        triggers=triggers,
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _to_ranking_read(
    ranking, repo: MissionRepository
) -> MissionCandidateRankingRead:
    data = MissionCandidateRankingRead.model_validate(ranking)
    data.entries = [
        MissionCandidateRankingEntryRead.model_validate(e)
        for e in repo.list_ranking_entries(ranking.id)
    ]
    return data


def _to_mission_read(
    mission, repo: MissionRepository
) -> MissionAssignmentRead:
    data = MissionAssignmentRead.model_validate(mission)
    data.participants = [
        MissionParticipantRead.model_validate(p)
        for p in repo.list_participants(mission.id)
    ]
    return data


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
    ranking = service.get_ranking(year=year, month=month)
    if ranking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ranking_not_found",
                "message": f"No ranking found for {year}/{month:02d}.",
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
        primary=[
            MissionCandidateRankingEntryRead.model_validate(e)
            for e in result["primary"]
        ],
        alternates=[
            MissionCandidateRankingEntryRead.model_validate(e)
            for e in result["alternates"]
        ],
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
        data.participants = [
            MissionParticipantRead.model_validate(p)
            for p in participants_by_mission.get(m.id, [])
        ]
        items.append(data)
    return items


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
