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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No has iniciado sesión o tu sesión expiró.")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión no es válida. Inicia sesión de nuevo.",
        ) from exc

    user_id = str(payload.get("sub") or "")
    token_version = int(payload.get("token_version") or 0)
    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.active or user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tu sesión no es válida. Inicia sesión de nuevo.")
    return user


def require_ready_user(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> UserModel:
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu contraseña antes de continuar.",
        )
    return current_user


def require_admin(
    current_user: Annotated[UserModel, Depends(require_ready_user)],
) -> UserModel:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol de administrador para esta acción.")
    return current_user


def require_encargado_or_admin(
    current_user: Annotated[UserModel, Depends(require_ready_user)],
) -> UserModel:
    if current_user.role not in {"encargado", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de encargado o administrador.",
        )
    return current_user


def require_permission(permission: str):
    """
    FastAPI dependency factory.
    Admins (role == "admin") automatically pass any permission check.
    Encargados must have the specific permission string in their permissions array.
    """
    def _check(
        current_user: Annotated[UserModel, Depends(require_ready_user)],
    ) -> UserModel:
        if current_user.role == "admin":
            return current_user
        if permission not in (current_user.permissions or []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para realizar esta acción.",
            )
        return current_user
    return _check


def require_superadmin(
    current_user: Annotated[UserModel, Depends(require_admin)],
) -> UserModel:
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de superadmin para esta acción.",
        )
    return current_user
