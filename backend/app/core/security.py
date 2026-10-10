import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
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


# ---------------------------------------------------------------------------
# Password policy — one place decides, both flows obey
# ---------------------------------------------------------------------------

PASSWORD_MIN_LENGTH = 8
_SPECIAL_CHARS = r"[!@#$%^&*(),.\-:;<>?/\\[\]{}_~`|'\"]"


class PasswordProblem(StrEnum):
    """Why a password was rejected. Each one has its own message for the user."""

    TOO_SHORT = "password_too_short"
    NO_UPPERCASE = "password_no_uppercase"
    NO_LOWERCASE = "password_no_lowercase"
    NO_DIGIT = "password_no_digit"
    NO_SPECIAL = "password_no_special"
    SAME_AS_CURRENT = "password_same_as_current"
    REUSED = "password_reused"
    CURRENT_INCORRECT = "password_current_incorrect"


PASSWORD_MESSAGES: dict[PasswordProblem, str] = {
    PasswordProblem.TOO_SHORT: (
        f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
    ),
    PasswordProblem.NO_UPPERCASE: "La contraseña debe contener al menos una mayúscula.",
    PasswordProblem.NO_LOWERCASE: "La contraseña debe contener al menos una minúscula.",
    PasswordProblem.NO_DIGIT: "La contraseña debe contener al menos un número.",
    PasswordProblem.NO_SPECIAL: "La contraseña debe contener al menos un carácter especial.",
    PasswordProblem.SAME_AS_CURRENT: "La contraseña nueva no puede ser igual a la actual.",
    PasswordProblem.REUSED: "No puedes reutilizar una contraseña reciente. Elige una nueva.",
    PasswordProblem.CURRENT_INCORRECT: "La contraseña actual no es correcta.",
}


def describe_password_problem(problem: PasswordProblem) -> str:
    return PASSWORD_MESSAGES[problem]


def password_error_detail(problem: object) -> dict[str, str]:
    """Build the `{code, message}` body every password route answers with.

    The client reads `message` verbatim, so the user is told the actual cause instead
    of a single generic sentence that fits none of the cases.
    """
    if isinstance(problem, PasswordProblem):
        return {"code": problem.value, "message": describe_password_problem(problem)}
    return {
        "code": "password_rejected",
        "message": "No se pudo cambiar la contraseña.",
    }


def check_password_strength(
    password: str,
    *,
    current_password: str | None = None,
    recent_hashes: Iterable[str] = (),
) -> PasswordProblem | None:
    """Return the first reason `password` is unacceptable, or None when it passes.

    Both password flows used to duplicate these rules and drifted; this is now the
    only definition. Checks run cheapest-first so the user is told the most basic
    thing to fix rather than an arbitrary one.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return PasswordProblem.TOO_SHORT
    if not re.search(r"[A-Z]", password):
        return PasswordProblem.NO_UPPERCASE
    if not re.search(r"[a-z]", password):
        return PasswordProblem.NO_LOWERCASE
    if not re.search(r"\d", password):
        return PasswordProblem.NO_DIGIT
    if not re.search(_SPECIAL_CHARS, password):
        return PasswordProblem.NO_SPECIAL
    if current_password is not None and password == current_password:
        return PasswordProblem.SAME_AS_CURRENT
    for old_hash in recent_hashes:
        if verify_password(password, old_hash):
            return PasswordProblem.REUSED
    return None


def create_access_token(subject: str, role: str, token_version: int) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "token_version": token_version,
        "aud": settings.token_audience,
        "iss": settings.token_issuer,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        audience=settings.token_audience,
        issuer=settings.token_issuer,
    )

