from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from backend.app.core.config import settings
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.email.resend import send_email
from backend.app.infrastructure.email.templates.invitation import render_invitation_email
from backend.app.infrastructure.email.templates.recovery import render_recovery_email
from backend.app.infrastructure.email.templates.reset import render_reset_email
from backend.app.infrastructure.repositories.set_password_tokens import (
    SetPasswordTokenRepository,
)

TOKEN_EXPIRE_HOURS = 48
SELF_SERVICE_RECOVERY_MINUTES = 30


def _hash_token(raw: str) -> str:
    return sha256(raw.encode()).hexdigest()


class InvitationService:
    def __init__(self, token_repo: SetPasswordTokenRepository) -> None:
        self.token_repo = token_repo

    def create_invitation(self, *, user: UserModel, created_by: UserModel) -> str:
        """Generate token, store hash, send email. Returns the raw token."""
        raw_token = token_urlsafe(48)
        now = datetime.now(UTC)
        token_record = SetPasswordTokenModel(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            email=user.email,
            expires_at=now + timedelta(hours=TOKEN_EXPIRE_HOURS),
            used_at=None,
            created_by=created_by.id,
            created_at=now,
        )
        self.token_repo.add(token_record)

        link = f"{settings.frontend_origin}/set-password?token={raw_token}"
        html = render_invitation_email(name=user.name, link=link, origin=settings.frontend_origin)
        send_email(to=user.email, subject="Invitación — Sistema de Turnos Médicos", html=html)

        return raw_token

    def create_reset(self, *, user: UserModel, created_by: UserModel) -> str:
        """Generate reset token, store hash, send email. Returns the raw token."""
        raw_token = token_urlsafe(48)
        now = datetime.now(UTC)
        token_record = SetPasswordTokenModel(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            email=user.email,
            expires_at=now + timedelta(hours=TOKEN_EXPIRE_HOURS),
            used_at=None,
            created_by=created_by.id,
            created_at=now,
        )
        self.token_repo.add(token_record)

        link = f"{settings.frontend_origin}/set-password?token={raw_token}"
        html = render_reset_email(name=user.name, link=link, origin=settings.frontend_origin)
        send_email(to=user.email, subject="Restablecer contraseña — Sistema de Turnos Médicos", html=html)

        return raw_token

    def create_self_service_recovery(self, *, user: UserModel) -> str:
        """Generate a self-service recovery token with 30-min expiry. Returns raw token."""
        raw_token = token_urlsafe(48)
        now = datetime.now(UTC)
        token_record = SetPasswordTokenModel(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            email=user.email,
            expires_at=now + timedelta(minutes=SELF_SERVICE_RECOVERY_MINUTES),
            used_at=None,
            created_by=user.id,
            created_at=now,
        )
        self.token_repo.add(token_record)

        link = f"{settings.frontend_origin}/set-password?token={raw_token}"
        html = render_recovery_email(name=user.name, link=link, origin=settings.frontend_origin)
        send_email(
            to=user.email,
            subject="Recuperacion de contrasena — Sistema de Turnos Medicos",
            html=html,
        )
        return raw_token

    def validate_token(self, raw_token: str) -> SetPasswordTokenModel | None:
        """Find and validate a token. Returns the token record if valid, None otherwise."""
        token_hash = _hash_token(raw_token)
        tokens = self.token_repo.list_valid()
        for token in tokens:
            if token.token_hash == token_hash:
                return token
        return None

    def mark_used(self, token: SetPasswordTokenModel) -> None:
        token.used_at = datetime.now(UTC)
