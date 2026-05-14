from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramLinkTokenModel,
    TelegramUserLinkModel,
)


class TelegramRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- User Links ---

    def add_link(self, link: TelegramUserLinkModel) -> TelegramUserLinkModel:
        self.session.add(link)
        self.session.flush()
        return link

    def get_link_by_telegram_id(self, telegram_user_id: str) -> TelegramUserLinkModel | None:
        stmt = select(TelegramUserLinkModel).where(
            TelegramUserLinkModel.telegram_user_id == telegram_user_id,
            TelegramUserLinkModel.active.is_(True),
        )
        return self.session.scalars(stmt).first()

    def get_link_by_user_id(self, user_id: str) -> TelegramUserLinkModel | None:
        stmt = select(TelegramUserLinkModel).where(
            TelegramUserLinkModel.user_id == user_id,
            TelegramUserLinkModel.active.is_(True),
        )
        return self.session.scalars(stmt).first()

    # --- Link Tokens ---

    def add_link_token(self, token: TelegramLinkTokenModel) -> TelegramLinkTokenModel:
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_token(self, token_str: str) -> TelegramLinkTokenModel | None:
        stmt = select(TelegramLinkTokenModel).where(
            TelegramLinkTokenModel.token == token_str,
            TelegramLinkTokenModel.active.is_(True),
            TelegramLinkTokenModel.used_at.is_(None),
            TelegramLinkTokenModel.expires_at > datetime.now(UTC),
        )
        return self.session.scalars(stmt).first()

    def mark_token_used(self, token_id: str) -> None:
        token = self.session.get(TelegramLinkTokenModel, token_id)
        if token:
            token.used_at = datetime.now(UTC)
            self.session.flush()

    def list_link_tokens(self) -> list[TelegramLinkTokenModel]:
        stmt = select(TelegramLinkTokenModel).order_by(
            TelegramLinkTokenModel.created_at.desc()
        )
        return list(self.session.scalars(stmt))

    def list_pending_tokens_by_user(self, user_id: str) -> list[TelegramLinkTokenModel]:
        stmt = select(TelegramLinkTokenModel).where(
            TelegramLinkTokenModel.user_id == user_id,
            TelegramLinkTokenModel.active.is_(True),
            TelegramLinkTokenModel.used_at.is_(None),
            TelegramLinkTokenModel.expires_at > datetime.now(UTC),
        )
        return list(self.session.scalars(stmt))

    def list_links(self) -> list[TelegramUserLinkModel]:
        stmt = select(TelegramUserLinkModel).order_by(TelegramUserLinkModel.linked_at.desc())
        return list(self.session.scalars(stmt))

    # --- Interactions ---

    def add_interaction(self, interaction: TelegramInteractionModel) -> TelegramInteractionModel:
        self.session.add(interaction)
        self.session.flush()
        return interaction

    def list_interactions(
        self,
        telegram_user_id: str | None = None,
        limit: int = 50,
    ) -> list[TelegramInteractionModel]:
        stmt = (
            select(TelegramInteractionModel)
            .order_by(TelegramInteractionModel.created_at.desc())
            .limit(limit)
        )
        if telegram_user_id:
            stmt = stmt.where(TelegramInteractionModel.telegram_user_id == telegram_user_id)
        return list(self.session.scalars(stmt))

    # --- Sessions ---

    def get_session(self, telegram_user_id: str) -> dict | None:
        """Return session_state JSON for *telegram_user_id*, or None."""
        from backend.app.infrastructure.db.models.telegram_session import TelegramSessionModel

        stmt = select(TelegramSessionModel).where(
            TelegramSessionModel.telegram_user_id == telegram_user_id,
        )
        row = self.session.scalars(stmt).first()
        if row is None:
            return None
        return row.session_state

    def upsert_session(self, telegram_user_id: str, state: dict) -> None:
        """Insert or update session_state for *telegram_user_id*."""
        from datetime import UTC, datetime

        from backend.app.infrastructure.db.models.telegram_session import TelegramSessionModel

        row = self.session.get(TelegramSessionModel, telegram_user_id)
        if row is None:
            row = TelegramSessionModel(
                telegram_user_id=telegram_user_id,
                session_state=state,
                created_at=datetime.now(UTC),
            )
            self.session.add(row)
        else:
            row.session_state = state
        self.session.flush()

    def delete_session(self, telegram_user_id: str) -> None:
        """Remove persisted session for *telegram_user_id*."""
        from backend.app.infrastructure.db.models.telegram_session import TelegramSessionModel

        row = self.session.get(TelegramSessionModel, telegram_user_id)
        if row is not None:
            self.session.delete(row)
            self.session.flush()
