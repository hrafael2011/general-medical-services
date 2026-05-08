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

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_RATE_LIMIT = 20
_LOGIN_WINDOW_SECONDS = 900  # 15 minutes


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
