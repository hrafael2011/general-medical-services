from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.application.accounts.errors import (
    DeletedEmailConflictError,
    DuplicateEmailError,
    PermissionDeniedError,
    UserNotFoundError,
)
from backend.app.application.accounts.invitation_service import InvitationService
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.set_password_tokens import (
    SetPasswordTokenRepository,
)
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.schemas.accounts import (
    CreateEncargadoRequest,
    ResetPasswordRequest,
    TemporaryPasswordResponse,
    UpdateUserRequest,
    UserRead,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def get_account_service(session: Annotated[Session, Depends(get_db_session)]) -> AccountService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    return AccountService(UserRepository(session), audit=AuditService(AuditRepository(session)))


@router.get("", response_model=list[UserRead])
def list_users(
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    role: str | None = Query(default=None),
) -> list[UserRead]:
    """List system users, optionally filtered by role."""
    repo = UserRepository(session)
    if role:
        users = repo.list_by_role(role)
    else:
        users = repo.list_by_role("encargado")  # sensible default for admin panel
    return [UserRead.model_validate(u) for u in users]


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
            permissions=payload.permissions,
        )
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_exists",
                "message": "Este correo ya existe. Usa otro correo o edita el usuario existente.",
            },
        ) from exc
    except DeletedEmailConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "email_belongs_to_deleted_user",
                "message": "Este correo pertenece a un usuario eliminado. Usa otro correo o restaura el usuario eliminado.",
            },
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.") from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios encargado pueden ser restablecidos.",
        ) from exc
    session.commit()
    return TemporaryPasswordResponse(
        user=UserRead.model_validate(result.user),
        temporary_password=result.temporary_password,
    )


@router.post("/{user_id}/invite", status_code=status.HTTP_200_OK)
def invite_user(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Send invitation email to an encargado user."""
    repo = UserRepository(session)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    if user.role not in ("encargado",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo usuarios encargado pueden ser invitados.",
        )

    token_repo = SetPasswordTokenRepository(session)
    service = InvitationService(token_repo)
    service.create_invitation(user=user, created_by=admin)
    session.commit()
    return {"message": "Invitation sent", "email": user.email}


@router.post("/{user_id}/send-reset", status_code=status.HTTP_200_OK)
def send_reset_email(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Send password reset email to an encargado user."""
    repo = UserRepository(session)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    if user.role not in ("encargado",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo usuarios encargado pueden recibir restablecimiento.",
        )

    token_repo = SetPasswordTokenRepository(session)
    service = InvitationService(token_repo)
    service.create_reset(user=user, created_by=admin)
    session.commit()
    return {"message": "Reset email sent", "email": user.email}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.soft_delete_user(actor=admin, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Usuario no encontrado."},
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "No se puede eliminar este usuario."},
        ) from exc
    session.commit()


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRead:
    try:
        updated = service.update_user(
            actor=admin,
            user_id=user_id,
            name=payload.name,
            role=payload.role,
            active=payload.active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Usuario no encontrado."},
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "No se puede actualizar este usuario."},
        ) from exc
    session.commit()
    return UserRead.model_validate(updated)
