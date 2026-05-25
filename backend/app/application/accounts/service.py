import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.application.accounts.errors import (
    AccountLockedError,
    DeletedEmailConflictError,
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidPasswordChangeError,
    PermissionDeniedError,
    UserNotFoundError,
)
from backend.app.application.audit.service import AuditService
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    generate_temporary_password,
    hash_password,
    verify_password,
)
from backend.app.domain.accounts import UserRole
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.users import UserRepository


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    user: UserModel


@dataclass(frozen=True)
class TemporaryPasswordResult:
    user: UserModel
    temporary_password: str


class AccountService:
    def __init__(self, users: UserRepository, audit: AuditService | None = None) -> None:
        self.users = users
        self.audit = audit

    def authenticate(self, email: str, password: str) -> LoginResult:
        user = self.users.get_by_email(email)
        now = datetime.now(UTC)
        if user is None:
            raise InvalidCredentialsError
        if user.locked_until is not None and user.locked_until > now:
            raise AccountLockedError
        if not user.active:
            raise InactiveUserError

        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            will_lock = user.failed_login_count >= settings.failed_login_lock_threshold
            if will_lock:
                user.locked_until = now + timedelta(minutes=settings.failed_login_lock_minutes)
            user.updated_at = now
            if self.audit is not None:
                self.audit.log_login_failed(email=email, locked=will_lock)
            raise InvalidCredentialsError

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        user.updated_at = now
        token = create_access_token(user.id, user.role, user.token_version)
        return LoginResult(access_token=token, user=user)

    def create_encargado(
        self,
        *,
        actor: UserModel,
        name: str,
        email: str,
        temporary_password: str | None = None,
        permissions: list[str] | None = None,
    ) -> TemporaryPasswordResult:
        self._require_admin(actor)
        password = temporary_password or generate_temporary_password()
        existing_user = self.users.get_by_email_including_deleted(email)
        if existing_user is not None:
            if existing_user.deleted_at is not None:
                raise DeletedEmailConflictError
            raise DuplicateEmailError

        now = datetime.now(UTC)
        user = UserModel(
            id=str(uuid4()),
            name=name.strip(),
            email=email.strip().lower(),
            role=UserRole.ENCARGADO.value,
            active=True,
            password_hash=hash_password(password),
            must_change_password=True,
            token_version=1,
            failed_login_count=0,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
            permissions=permissions or [],
            is_superadmin=False,
        )
        try:
            self.users.add(user)
        except IntegrityError as exc:
            raise DuplicateEmailError from exc
        self.users.add_password_history(user.id, user.password_hash)
        if self.audit is not None:
            self.audit.log_user_created(actor_id=actor.id, user=user)
        return TemporaryPasswordResult(user=user, temporary_password=password)

    def create_admin(
        self,
        *,
        actor: UserModel,
        name: str,
        email: str,
        temporary_password: str | None = None,
    ) -> TemporaryPasswordResult:
        self._require_superadmin(actor)
        password = temporary_password or generate_temporary_password()
        existing_user = self.users.get_by_email_including_deleted(email)
        if existing_user is not None:
            if existing_user.deleted_at is not None:
                raise DeletedEmailConflictError
            raise DuplicateEmailError

        now = datetime.now(UTC)
        user = UserModel(
            id=str(uuid4()),
            name=name.strip(),
            email=email.strip().lower(),
            role=UserRole.ADMIN.value,
            active=True,
            password_hash=hash_password(password),
            must_change_password=True,
            token_version=1,
            failed_login_count=0,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
            permissions=[],
            is_superadmin=False,
        )
        try:
            self.users.add(user)
        except IntegrityError as exc:
            raise DuplicateEmailError from exc
        self.users.add_password_history(user.id, user.password_hash)
        if self.audit is not None:
            self.audit.log_user_created(actor_id=actor.id, user=user)
        return TemporaryPasswordResult(user=user, temporary_password=password)

    def reset_encargado_password(
        self,
        *,
        actor: UserModel,
        user_id: str,
        temporary_password: str | None = None,
    ) -> TemporaryPasswordResult:
        self._require_admin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role != UserRole.ENCARGADO.value:
            raise PermissionDeniedError
        password = temporary_password or generate_temporary_password()
        now = datetime.now(UTC)
        new_hash = hash_password(password)
        user.password_hash = new_hash
        user.must_change_password = True
        user.token_version += 1
        user.failed_login_count = 0
        user.locked_until = None
        user.updated_at = now
        self.users.add_password_history(user.id, new_hash)
        if self.audit is not None:
            self.audit.log_password_reset(actor_id=actor.id, user=user)
        return TemporaryPasswordResult(user=user, temporary_password=password)

    def change_own_password(
        self,
        *,
        user: UserModel,
        current_password: str,
        new_password: str,
    ) -> UserModel:
        if not user.active:
            raise InactiveUserError
        if not verify_password(current_password, user.password_hash):
            raise InvalidPasswordChangeError
        if verify_password(new_password, user.password_hash):
            raise InvalidPasswordChangeError

        # Password complexity: at least 10 chars, 1 upper, 1 lower, 1 digit, 1 special
        if len(new_password) < 10:
            raise InvalidPasswordChangeError
        if not re.search(r"[A-Z]", new_password):
            raise InvalidPasswordChangeError
        if not re.search(r"[a-z]", new_password):
            raise InvalidPasswordChangeError
        if not re.search(r"\d", new_password):
            raise InvalidPasswordChangeError
        if not re.search(r"[!@#$%^&*(),.\-:;<>?/\\[\]{}_~`|'\"]", new_password):
            raise InvalidPasswordChangeError

        # Check against password history (last 5)
        recent_hashes = self.users.list_recent_password_hashes(user.id)
        for old_hash in recent_hashes:
            if verify_password(new_password, old_hash):
                raise InvalidPasswordChangeError
        new_hash = hash_password(new_password)

        now = datetime.now(UTC)
        user.password_hash = new_hash
        user.must_change_password = False
        user.password_changed_at = now
        user.token_version += 1
        user.updated_at = now

        # Save to password history
        self.users.add_password_history(user.id, new_hash)

        if self.audit is not None:
            self.audit.log_password_changed(actor_id=user.id, user=user)
        return user

    def ensure_admin_password(
        self,
        *,
        email: str,
        name: str,
        temporary_password: str | None = None,
    ) -> TemporaryPasswordResult:
        password = temporary_password or generate_temporary_password()
        now = datetime.now(UTC)
        user = self.users.get_by_email(email)
        if user is None:
            user = UserModel(
                id=str(uuid4()),
                name=name.strip(),
                email=email.strip().lower(),
                role=UserRole.ADMIN.value,
                active=True,
                password_hash=hash_password(password),
                must_change_password=True,
                token_version=1,
                failed_login_count=0,
                created_by=None,
                created_at=now,
                updated_at=now,
            )
            self.users.add(user)
        else:
            if user.role != UserRole.ADMIN.value:
                raise PermissionDeniedError
            user.password_hash = hash_password(password)
            user.must_change_password = True
            user.token_version += 1
            user.failed_login_count = 0
            user.locked_until = None
            user.active = True
            user.updated_at = now
        return TemporaryPasswordResult(user=user, temporary_password=password)

    def soft_delete_user(self, *, actor: UserModel, user_id: str) -> None:
        self._require_admin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role not in (UserRole.ENCARGADO.value, UserRole.ADMIN.value):
            raise PermissionDeniedError
        self.users.soft_delete(user_id)
        if self.audit is not None:
            self.audit.log_user_deleted(actor_id=actor.id, user=user)

    def update_user(
        self,
        *,
        actor: UserModel,
        user_id: str,
        name: str | None = None,
        role: str | None = None,
        active: bool | None = None,
        permissions: list[str] | None = None,
    ) -> UserModel:
        self._require_admin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role not in (UserRole.ENCARGADO.value, UserRole.ADMIN.value):
            raise PermissionDeniedError

        changed: dict[str, object] = {}
        if name is not None:
            user.name = name.strip()
            changed["name"] = user.name
        if role is not None:
            user.role = role
            changed["role"] = role
        if active is not None:
            user.active = active
            changed["active"] = active
        if permissions is not None:
            user.permissions = permissions
            changed["permissions"] = permissions

        if not changed:
            return user

        self.users.update(user_id, **changed)
        if self.audit is not None:
            self.audit.log_user_updated(actor_id=actor.id, user=user, changed_fields=changed)
        return user

    def make_superadmin(
        self,
        *,
        actor: UserModel,
        user_id: str,
    ) -> UserModel:
        self._require_superadmin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role != UserRole.ADMIN.value:
            raise PermissionDeniedError("Solo administradores pueden ser promovidos a superadmin.")
        user.is_superadmin = True
        user.updated_at = datetime.now(UTC)
        self.users.update(user_id, is_superadmin=True)
        if self.audit is not None:
            self.audit.log_user_updated(
                actor_id=actor.id, user=user,
                changed_fields={"is_superadmin": True},
            )
        return user

    def initiate_password_recovery(self, *, email: str) -> UserModel | None:
        """Look up user by email for password recovery. Returns None if not found or inactive."""
        user = self.users.get_by_email(email)
        if user is None:
            return None
        if not user.active:
            return None
        if user.role not in (UserRole.ENCARGADO.value, UserRole.ADMIN.value):
            return None
        return user

    def _require_admin(self, actor: UserModel) -> None:
        if actor.role != UserRole.ADMIN.value or not actor.active or actor.must_change_password:
            raise PermissionDeniedError

    def _require_superadmin(self, actor: UserModel) -> None:
        self._require_admin(actor)
        if not actor.is_superadmin:
            raise PermissionDeniedError("Se requiere rol de superadmin para esta acción.")
