from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserModel:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    user_id = str(payload.get("sub") or "")
    token_version = int(payload.get("token_version") or 0)
    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.active or user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user


def require_ready_user(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> UserModel:
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )
    return current_user


def require_admin(
    current_user: Annotated[UserModel, Depends(require_ready_user)],
) -> UserModel:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
