"""Telegram webhook and user-link management routes."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.infrastructure.db.models.telegram import TelegramUserLinkModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.schemas.telegram import (
    CreateTelegramLinkRequest,
    TelegramInteractionRead,
    TelegramUserLinkRead,
    TelegramWebhookUpdate,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------

def get_orchestrator(session: Annotated[Session, Depends(get_db_session)]):  # noqa: ANN201
    import os

    from backend.app.application.telegram.bot_client import FakeBotClient, TelegramBotClient
    from backend.app.application.telegram.intent_classifier import IntentClassifier
    from backend.app.application.telegram.llm import DeepSeekProvider, FakeLLMProvider
    from backend.app.application.telegram.orchestrator import TelegramOrchestrator
    from backend.app.application.telegram.tools import ToolGateway
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.users import UserRepository

    use_real = os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("DEEPSEEK_API_KEY")
    llm = DeepSeekProvider() if use_real else FakeLLMProvider()
    bot = TelegramBotClient() if os.environ.get("TELEGRAM_BOT_TOKEN") else FakeBotClient()

    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(session),
        user_repo=UserRepository(session),
        classifier=IntentClassifier(llm),
        tools=ToolGateway(
            doctor_repo=DoctorRepository(session),
            calendar_repo=CalendarRepository(session),
            mission_repo=MissionRepository(session),
            availability_repo=AvailabilityRepository(session),
        ),
        bot_client=bot,
        llm=llm,
    )


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=200)
def webhook(
    update: TelegramWebhookUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    orchestrator: Annotated[object, Depends(get_orchestrator)],
) -> dict:
    """Telegram Bot API webhook. Always returns 200 to avoid Telegram retries."""
    try:
        if update.message is None or update.message.text is None:
            return {"ok": True}

        if update.message.from_ is None:
            return {"ok": True}

        telegram_user_id = str(update.message.from_.id)
        telegram_username = update.message.from_.username
        chat_id = update.message.chat.id
        text = update.message.text

        orchestrator.handle_message(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            chat_id=chat_id,
            text=text,
        )
        session.commit()
    except Exception:
        pass  # Telegram requires HTTP 200 regardless of errors

    return {"ok": True}


# ---------------------------------------------------------------------------
# Link management (admin only)
# ---------------------------------------------------------------------------

@router.get("/links", response_model=list[TelegramUserLinkRead])
def list_links(
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[TelegramUserLinkRead]:
    """Return all Telegram user links."""
    repo = TelegramRepository(session)
    links = repo.list_links()
    return [TelegramUserLinkRead.model_validate(link) for link in links]


@router.post("/links", response_model=TelegramUserLinkRead, status_code=status.HTTP_201_CREATED)
def create_link(
    payload: CreateTelegramLinkRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> TelegramUserLinkRead:
    """Create a new Telegram user link."""
    repo = TelegramRepository(session)
    link = TelegramUserLinkModel(
        id=str(uuid.uuid4()),
        telegram_user_id=payload.telegram_user_id,
        telegram_username=payload.telegram_username,
        user_id=payload.user_id,
        active=True,
        linked_by=admin.id,
        linked_at=datetime.now(UTC),
        last_used_at=None,
    )
    repo.add_link(link)
    session.commit()
    return TelegramUserLinkRead.model_validate(link)


@router.delete("/links/{telegram_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_link(
    telegram_user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Deactivate a Telegram user link by telegram_user_id."""
    repo = TelegramRepository(session)
    link = repo.get_link_by_telegram_id(telegram_user_id)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "link_not_found",
                "message": f"No active link found for telegram_user_id={telegram_user_id}.",
            },
        )
    link.active = False
    session.commit()


# ---------------------------------------------------------------------------
# Interactions (admin only)
# ---------------------------------------------------------------------------

@router.get("/interactions", response_model=list[TelegramInteractionRead])
def list_interactions(
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
    telegram_user_id: str | None = None,
) -> list[TelegramInteractionRead]:
    """List recent Telegram interactions, optionally filtered by telegram_user_id."""
    repo = TelegramRepository(session)
    interactions = repo.list_interactions(telegram_user_id=telegram_user_id)
    return [TelegramInteractionRead.model_validate(i) for i in interactions]
