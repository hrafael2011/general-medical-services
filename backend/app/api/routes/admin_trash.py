from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.application.admin.trash_service import TrashService, TrashServiceError
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.users import UserRepository

router = APIRouter(prefix="/admin/trash", tags=["admin-trash"])


def get_trash_service(session: Annotated[Session, Depends(get_db_session)]) -> TrashService:
    return TrashService(
        DoctorRepository(session),
        UserRepository(session),
        CatalogRepository(session),
        audit=AuditRepository(session),
    )


@router.get("")
def list_trash(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_trash"))],
    service: Annotated[TrashService, Depends(get_trash_service)],
    type: str,
):
    try:
        items = service.list_deleted(type)
    except TrashServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    result = []
    for item in items:
        data = {
            "id": item.id,
            "name": getattr(item, "name", getattr(item, "display_name", "")),
            "deleted_at": item.deleted_at.isoformat() if item.deleted_at else None,
        }
        if type == "doctors":
            data["rank_name"] = getattr(item, "rank_id", None)
        elif type == "users":
            data["email"] = getattr(item, "email", "")
            data["role"] = getattr(item, "role", "")
        elif type == "ranks":
            data["abbreviation"] = getattr(item, "abbreviation", "")
        elif type == "departments":
            data["normalized_name"] = getattr(item, "normalized_name", "")
        elif type == "deactivation_reasons":
            data["code"] = getattr(item, "code", "")
        result.append(data)
    return result


@router.get("/counts")
def get_trash_counts(
    _current_user: Annotated[UserModel, Depends(require_permission("manage_trash"))],
    service: Annotated[TrashService, Depends(get_trash_service)],
):
    return {
        "doctors": len(service.list_deleted("doctors")),
        "users": len(service.list_deleted("users")),
        "ranks": len(service.list_deleted("ranks")),
        "departments": len(service.list_deleted("departments")),
        "deactivation_reasons": len(service.list_deleted("deactivation_reasons")),
    }


@router.post("/{entity_type}/{entity_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_entity(
    entity_type: str,
    entity_id: str,
    _current_user: Annotated[UserModel, Depends(require_permission("manage_trash"))],
    service: Annotated[TrashService, Depends(get_trash_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.restore(entity_type, entity_id)
    except TrashServiceError as exc:
        raise HTTPException(
            status_code=_TRASH_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from exc
    session.commit()


_TRASH_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "not_deleted": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "invalid_type": status.HTTP_400_BAD_REQUEST,
    "integrity_violation": status.HTTP_409_CONFLICT,
}


@router.delete("/{entity_type}/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_entity(
    entity_type: str,
    entity_id: str,
    _current_user: Annotated[UserModel, Depends(require_permission("manage_trash"))],
    service: Annotated[TrashService, Depends(get_trash_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.hard_delete(entity_type, entity_id)
    except TrashServiceError as exc:
        raise HTTPException(
            status_code=_TRASH_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from exc
    session.commit()
