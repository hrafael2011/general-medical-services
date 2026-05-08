import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.user import PasswordHistoryModel, UserModel

PASSWORD_HISTORY_DEPTH = 5


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: UserModel) -> UserModel:
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_id(self, user_id: str) -> UserModel | None:
        return self.session.get(UserModel, user_id)

    def get_by_email(self, email: str) -> UserModel | None:
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(UserModel.email == normalized_email)
        return self.session.scalar(statement)

    def list_by_role(self, role: str) -> list[UserModel]:
        statement = select(UserModel).where(UserModel.role == role).order_by(UserModel.name)
        return list(self.session.scalars(statement))

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

