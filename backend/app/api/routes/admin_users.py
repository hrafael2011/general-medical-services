from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.application.accounts.errors import (
    DuplicateEmailError,
    PermissionDeniedError,
    UserNotFoundError,
)
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.schemas.accounts import (
    CreateEncargadoRequest,
    ResetPasswordRequest,
    TemporaryPasswordResponse,
    UserRead,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def get_account_service(session: Annotated[Session, Depends(get_db_session)]) -> AccountService:
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.application.audit.service import AuditService
    return AccountService(UserRepository(session), audit=AuditService(AuditRepository(session)))


@router.post(
    "/encargados",
    response_model=TemporaryPasswordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_encargado(
    payload: CreateEncargadoRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TemporaryPasswordResponse:
    try:
        result = service.create_encargado(
            actor=admin,
            name=payload.name,
            email=payload.email,
            temporary_password=payload.temporary_password,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from exc
    session.commit()
    return TemporaryPasswordResponse(
        user=UserRead.model_validate(result.user),
        temporary_password=result.temporary_password,
    )


@router.post("/{user_id}/reset-password", response_model=TemporaryPasswordResponse)
def reset_encargado_password(
    user_id: str,
    payload: ResetPasswordRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TemporaryPasswordResponse:
    try:
        result = service.reset_encargado_password(
            actor=admin,
            user_id=user_id,
            temporary_password=payload.temporary_password,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only encargado users can be reset",
        ) from exc
    session.commit()
    return TemporaryPasswordResponse(
        user=UserRead.model_validate(result.user),
        temporary_password=result.temporary_password,
    )
