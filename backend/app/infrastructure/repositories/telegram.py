from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.infrastructure.db.models.telegram import (
    TelegramUserLinkModel, TelegramInteractionModel,
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
            TelegramUserLinkModel.active == True,  # noqa: E712
        )
        return self.session.scalars(stmt).first()

    def get_link_by_user_id(self, user_id: str) -> TelegramUserLinkModel | None:
        stmt = select(TelegramUserLinkModel).where(
            TelegramUserLinkModel.user_id == user_id,
            TelegramUserLinkModel.active == True,  # noqa: E712
        )
        return self.session.scalars(stmt).first()

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
