import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramLinkTokenModel,
    TelegramUserLinkModel,
)
from backend.app.infrastructure.db.models.user import PasswordHistoryModel, UserModel

PASSWORD_HISTORY_DEPTH = 5


def _not_deleted() -> tuple:
    return (UserModel.deleted_at.is_(None),)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: UserModel) -> UserModel:
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_id(self, user_id: str) -> UserModel | None:
        stmt = select(UserModel).where(
            UserModel.id == user_id, *_not_deleted()
        )
        return self.session.scalars(stmt).first()

    def get_by_email(self, email: str) -> UserModel | None:
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(
            UserModel.email == normalized_email, *_not_deleted()
        )
        return self.session.scalar(statement)

    def get_by_email_including_deleted(self, email: str) -> UserModel | None:
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(UserModel.email == normalized_email)
        return self.session.scalar(statement)

    def list_by_role(self, role: str) -> list[UserModel]:
        statement = (
            select(UserModel)
            .where(UserModel.role == role, *_not_deleted())
            .order_by(UserModel.name)
        )
        return list(self.session.scalars(statement))

    def list_all(self) -> list[UserModel]:
        statement = (
            select(UserModel)
            .where(*_not_deleted())
            .order_by(UserModel.name)
        )
        return list(self.session.scalars(statement))

    def list_deleted(self) -> list[UserModel]:
        stmt = (
            select(UserModel)
            .where(UserModel.deleted_at.isnot(None))
            .order_by(UserModel.deleted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def soft_delete(self, user_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(deleted_at=now, updated_at=now)
        )
        self.session.flush()

    def restore(self, user_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(deleted_at=None, updated_at=now)
        )
        self.session.flush()

    def get_by_id_including_deleted(self, user_id: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        return self.session.scalars(stmt).first()

    def hard_delete(self, user_id: str) -> None:
        user = self.get_by_id_including_deleted(user_id)
        if user is not None:
            self.session.execute(
                delete(PasswordHistoryModel).where(PasswordHistoryModel.user_id == user_id)
            )
            self.session.execute(
                delete(SetPasswordTokenModel).where(SetPasswordTokenModel.user_id == user_id)
            )
            self.session.execute(
                delete(TelegramLinkTokenModel).where(TelegramLinkTokenModel.user_id == user_id)
            )
            self.session.execute(
                delete(TelegramUserLinkModel).where(TelegramUserLinkModel.user_id == user_id)
            )
            self.session.execute(
                update(ActionAlertModel)
                .where(ActionAlertModel.created_by == user_id)
                .values(created_by=None)
            )
            self.session.execute(
                update(ActionAlertModel)
                .where(ActionAlertModel.resolved_by == user_id)
                .values(resolved_by=None)
            )
            self.session.execute(
                update(ActionAlertModel)
                .where(ActionAlertModel.dismissed_by == user_id)
                .values(dismissed_by=None)
            )
            self.session.execute(
                update(ConfirmationRequestModel)
                .where(ConfirmationRequestModel.created_by == user_id)
                .values(created_by=None)
            )
            self.session.execute(
                update(TelegramInteractionModel)
                .where(TelegramInteractionModel.matched_user_id == user_id)
                .values(matched_user_id=None)
            )
            self.session.execute(
                update(TelegramLinkTokenModel)
                .where(TelegramLinkTokenModel.created_by == user_id)
                .values(created_by=None)
            )
            self.session.delete(user)
            self.session.flush()

    def update(self, user_id: str, **fields: object) -> None:
        now = datetime.now(UTC)
        values = {**fields, "updated_at": now}
        self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(**values)
        )
        self.session.flush()

    # --- Password History ---

    def list_recent_password_hashes(self, user_id: str) -> list[str]:
        """Return the last PASSWORD_HISTORY_DEPTH password hashes for a user."""
        stmt = (
            select(PasswordHistoryModel.password_hash)
            .where(PasswordHistoryModel.user_id == user_id)
            .order_by(PasswordHistoryModel.created_at.desc())
            .limit(PASSWORD_HISTORY_DEPTH)
        )
        return list(self.session.scalars(stmt))

    def add_password_history(self, user_id: str, password_hash: str) -> None:
        entry = PasswordHistoryModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self.session.add(entry)
