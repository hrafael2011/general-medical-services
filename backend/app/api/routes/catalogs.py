from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin, require_ready_user
from backend.app.application.catalogs.service import CatalogError, CatalogService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.schemas.catalogs import (
    CreateDeactivationReasonRequest,
    CreateDepartmentRequest,
    CreateRankRequest,
    DeleteDeactivationReasonResponse,
    DeactivationReasonRead,
    DeleteDepartmentResponse,
    DeleteRankResponse,
    DepartmentRead,
    RankRead,
    ServiceAreaRead,
    UpdateDeactivationReasonRequest,
    UpdateDepartmentRequest,
    UpdateRankRequest,
)

router = APIRouter(prefix="/catalogs", tags=["catalogs"])


def get_catalog_service(session: Annotated[Session, Depends(get_db_session)]) -> CatalogService:
    return CatalogService(CatalogRepository(session))


@router.post("/seed", status_code=status.HTTP_204_NO_CONTENT)
def seed_catalogs(
    _user: Annotated[UserModel, Depends(require_admin)],
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


@router.post(
    "/deactivation-reasons",
    response_model=DeactivationReasonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_deactivation_reason(
    payload: CreateDeactivationReasonRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DeactivationReasonRead:
    reason = service.create_deactivation_reason(
        display_name=payload.display_name,
        applies_to_sex=payload.applies_to_sex,
    )
    session.commit()
    return DeactivationReasonRead.model_validate(reason)


@router.patch("/deactivation-reasons/{reason_id}", response_model=DeactivationReasonRead)
def update_deactivation_reason(
    reason_id: str,
    payload: UpdateDeactivationReasonRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DeactivationReasonRead:
    try:
        reason = service.update_deactivation_reason(
            reason_id,
            **payload.model_dump(exclude_unset=True),
        )
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return DeactivationReasonRead.model_validate(reason)


@router.delete("/deactivation-reasons/{reason_id}", response_model=DeleteDeactivationReasonResponse)
def delete_deactivation_reason(
    reason_id: str,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DeleteDeactivationReasonResponse:
    try:
        affected = service.soft_delete_deactivation_reason(reason_id)
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return DeleteDeactivationReasonResponse(
        message="Deactivation reason deleted",
        affected_doctors=affected,
    )


@router.get("/ranks", response_model=list[RankRead])
def list_ranks(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[RankRead]:
    ranks = CatalogRepository(session).list_ranks()
    return [RankRead.model_validate(rank) for rank in ranks]


@router.post("/ranks", response_model=RankRead, status_code=status.HTTP_201_CREATED)
def create_rank(
    payload: CreateRankRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RankRead:
    rank = service.create_rank(payload.name, payload.abbreviation)
    session.commit()
    return RankRead.model_validate(rank)


@router.patch("/ranks/{rank_id}", response_model=RankRead)
def update_rank(
    rank_id: str,
    payload: UpdateRankRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> RankRead:
    try:
        rank = service.update_rank(
            rank_id,
            name=payload.name,
            abbreviation=payload.abbreviation,
            active=payload.active,
        )
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return RankRead.model_validate(rank)


@router.delete("/ranks/{rank_id}", response_model=DeleteRankResponse)
def delete_rank(
    rank_id: str,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DeleteRankResponse:
    try:
        affected = service.soft_delete_rank(rank_id)
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return DeleteRankResponse(message="Rank deleted", affected_doctors=affected)


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    _user: Annotated[UserModel, Depends(require_ready_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[DepartmentRead]:
    departments = CatalogRepository(session).list_departments()
    return [DepartmentRead.model_validate(department) for department in departments]


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: CreateDepartmentRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DepartmentRead:
    department = service.create_department(payload.name)
    session.commit()
    return DepartmentRead.model_validate(department)


@router.patch("/departments/{department_id}", response_model=DepartmentRead)
def update_department(
    department_id: str,
    payload: UpdateDepartmentRequest,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DepartmentRead:
    try:
        department = service.update_department(
            department_id,
            name=payload.name,
            active=payload.active,
        )
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return DepartmentRead.model_validate(department)


@router.delete("/departments/{department_id}", response_model=DeleteDepartmentResponse)
def delete_department(
    department_id: str,
    _user: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> DeleteDepartmentResponse:
    try:
        affected = service.soft_delete_department(department_id)
    except CatalogError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    session.commit()
    return DeleteDepartmentResponse(message="Department deleted", affected_doctors=affected)
