from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.user import UserModel


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

