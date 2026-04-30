from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import jwt
from pwdlib import PasswordHash

from backend.app.core.config import settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def generate_temporary_password() -> str:
    return token_urlsafe(18)


def create_access_token(subject: str, role: str, token_version: int) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "token_version": token_version,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

