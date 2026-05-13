from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel


class SetPasswordTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, token: SetPasswordTokenModel) -> None:
        self.session.add(token)

    def list_valid(self) -> list[SetPasswordTokenModel]:
        now = datetime.now(UTC)
        return (
            self.session.query(SetPasswordTokenModel)
            .filter(
                SetPasswordTokenModel.expires_at > now,
                SetPasswordTokenModel.used_at.is_(None),
            )
            .all()
        )
