from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.application.accounts.errors import (
    AccountLockedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidPasswordChangeError,
)
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.models.user import LoginAttemptModel, UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.schemas.accounts import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserRead,
)
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_RATE_LIMIT = 20
_LOGIN_WINDOW_SECONDS = 900  # 15 minutes


class SetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=10)


class SetPasswordValidateResponse(BaseModel):
    valid: bool
    email: str | None = None
    name: str | None = None
    expires_at: datetime | None = None


def _check_login_rate_limit(session: Session, client_ip: str) -> None:
    now = datetime.now(UTC)
    cutoff = now.timestamp() - _LOGIN_WINDOW_SECONDS
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)

    # Prune old attempts for this IP
    delete_stmt = select(LoginAttemptModel).where(
        LoginAttemptModel.ip_address == client_ip,
        LoginAttemptModel.attempted_at < cutoff_dt,
    )
    old_attempts = list(session.scalars(delete_stmt))
    for a in old_attempts:
        session.delete(a)

    # Count recent attempts
    count_stmt = select(LoginAttemptModel).where(
        LoginAttemptModel.ip_address == client_ip,
        LoginAttemptModel.attempted_at >= cutoff_dt,
    )
    recent = list(session.scalars(count_stmt))
    if len(recent) >= _LOGIN_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de login. Intenta de nuevo en 15 minutos.",
        )

    # Record this attempt
    attempt = LoginAttemptModel(
        id=str(uuid4()),
        ip_address=client_ip,
        attempted_at=now,
        success=False,
    )
    session.add(attempt)


def get_account_service(session: Annotated[Session, Depends(get_db_session)]) -> AccountService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    return AccountService(UserRepository(session), audit=AuditService(AuditRepository(session)))


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    payload: LoginRequest,
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
    _check_login_rate_limit(
        session,
        request.client.host if request.client else "unknown",
    )
    try:
        result = service.authenticate(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        ) from exc
    except AccountLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked",
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive account",
        ) from exc
    session.commit()
    return LoginResponse(
        access_token=result.access_token,
        user=UserRead.model_validate(result.user),
    )


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[UserModel, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/change-password", response_model=UserRead)
def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[UserModel, Depends(get_current_user)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRead:
    try:
        user = service.change_own_password(
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except InvalidPasswordChangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password change",
        ) from exc
    session.commit()
    return UserRead.model_validate(user)


@router.get("/set-password")
def validate_set_password_token(
    token: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> SetPasswordValidateResponse:
    """Validate a set-password token and return user info."""
    from backend.app.application.accounts.invitation_service import InvitationService
    from backend.app.infrastructure.repositories.set_password_tokens import (
        SetPasswordTokenRepository,
    )
    from backend.app.infrastructure.repositories.users import UserRepository

    token_repo = SetPasswordTokenRepository(session)
    service = InvitationService(token_repo)
    token_record = service.validate_token(token)

    if token_record is None:
        return SetPasswordValidateResponse(valid=False)

    user_repo = UserRepository(session)
    user = user_repo.get_by_id(token_record.user_id)
    if user is None:
        return SetPasswordValidateResponse(valid=False)

    return SetPasswordValidateResponse(
        valid=True,
        email=token_record.email,
        name=user.name,
        expires_at=token_record.expires_at,
    )


@router.post("/set-password", status_code=status.HTTP_200_OK)
def set_password(
    payload: SetPasswordRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Set password using a valid token."""
    import re

    from backend.app.application.accounts.invitation_service import InvitationService
    from backend.app.core.security import hash_password
    from backend.app.infrastructure.repositories.set_password_tokens import (
        SetPasswordTokenRepository,
    )
    from backend.app.infrastructure.repositories.users import UserRepository

    token_repo = SetPasswordTokenRepository(session)
    service = InvitationService(token_repo)
    token_record = service.validate_token(payload.token)

    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enlace inválido o expirado. Contacta al administrador.",
        )

    user_repo = UserRepository(session)
    user = user_repo.get_by_id(token_record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate password complexity
    if not re.search(r"[A-Z]", payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos una mayúscula",
        )
    if not re.search(r"[a-z]", payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos una minúscula",
        )
    if not re.search(r"\d", payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos un número",
        )
    if not re.search(r"[!@#$%^&*(),.\-:;<>?/\\[\]{}_~`|'\"]", payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe contener al menos un carácter especial",
        )

    # Set the password
    new_hash = hash_password(payload.password)
    user.password_hash = new_hash
    user.must_change_password = False
    user.token_version += 1
    user.updated_at = datetime.now(UTC)

    service.mark_used(token_record)
    session.commit()

    return {"message": "Contraseña creada exitosamente. Ahora puedes iniciar sesión."}
