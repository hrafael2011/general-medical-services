from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_ready_user
from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.schemas.catalogs import (
    CalendarGenerationSettingsRead,
    CreateDepartmentRequest,
    CreateRankRequest,
    DeactivationReasonRead,
    DepartmentRead,
    RankRead,
    ServiceAreaRead,
    SystemSettingRead,
    UpdateCalendarGenerationSettingsRequest,
)

router = APIRouter(prefix="/catalogs", tags=["catalogs"])


def get_catalog_service(session: Annotated[Session, Depends(get_db_session)]) -> CatalogService:
    return CatalogService(CatalogRepository(session))


@router.post("/seed", status_code=204)
def seed_catalogs(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    service.seed_initial_catalogs()
    session.commit()


@router.get("/service-areas", response_model=list[ServiceAreaRead])
def list_service_areas(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[ServiceAreaRead]:
    areas = CatalogRepository(session).list_service_areas()
    return [ServiceAreaRead.model_validate(area) for area in areas]


@router.get("/deactivation-reasons", response_model=list[DeactivationReasonRead])
def list_deactivation_reasons(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
    sex: Annotated[str | None, Query(pattern="^(female|male)$")] = None,
) -> list[DeactivationReasonRead]:
    repository = CatalogRepository(session)
    if sex is None:
        reasons = repository.list_deactivation_reasons()
    else:
        reasons = repository.list_deactivation_reasons_for_sex(sex)
    return [DeactivationReasonRead.model_validate(reason) for reason in reasons]


@router.get("/ranks", response_model=list[RankRead])
def list_ranks(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RankRead]:
    ranks = CatalogRepository(session).list_ranks()
    return [RankRead.model_validate(rank) for rank in ranks]


@router.post("/ranks", response_model=RankRead, status_code=201)
def create_rank(
    payload: CreateRankRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RankRead:
    rank = service.create_rank(payload.name, payload.abbreviation)
    session.commit()
    return RankRead.model_validate(rank)


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[DepartmentRead]:
    departments = CatalogRepository(session).list_departments()
    return [DepartmentRead.model_validate(department) for department in departments]


@router.post("/departments", response_model=DepartmentRead, status_code=201)
def create_department(
    payload: CreateDepartmentRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DepartmentRead:
    department = service.create_department(payload.name)
    session.commit()
    return DepartmentRead.model_validate(department)


@router.get("/settings/calendar-generation-day", response_model=SystemSettingRead)
def get_calendar_generation_day(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> SystemSettingRead:
    repository = CatalogRepository(session)
    setting = repository.get_setting("calendar_generation_day")
    if setting is None:
        CatalogService(repository).seed_initial_catalogs()
        session.commit()
        setting = repository.get_setting("calendar_generation_day")
    return SystemSettingRead.model_validate(setting)


@router.get("/settings/calendar-generation", response_model=CalendarGenerationSettingsRead)
def get_calendar_generation_settings(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarGenerationSettingsRead:
    settings = service.get_calendar_generation_settings()
    session.commit()
    return CalendarGenerationSettingsRead.model_validate(settings)


@router.patch("/settings/calendar-generation", response_model=CalendarGenerationSettingsRead)
def update_calendar_generation_settings(
    payload: UpdateCalendarGenerationSettingsRequest,
    _user: Annotated[UserModel, Depends(require_ready_user)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CalendarGenerationSettingsRead:
    settings = service.update_calendar_generation_settings(
        auto_generation_enabled=payload.auto_generation_enabled,
        generation_day=payload.generation_day,
    )
    session.commit()
    return CalendarGenerationSettingsRead.model_validate(settings)
