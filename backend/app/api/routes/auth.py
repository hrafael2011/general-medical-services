from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.application.accounts.errors import (
    AccountLockedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidPasswordChangeError,
)
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.schemas.accounts import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_account_service(session: Annotated[Session, Depends(get_db_session)]) -> AccountService:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository
    return AccountService(UserRepository(session), audit=AuditService(AuditRepository(session)))


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> LoginResponse:
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
