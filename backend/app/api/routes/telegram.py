"""Telegram webhook and user-link management routes."""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.application.telegram.memory import SessionStore
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.telegram import (
    TelegramLinkTokenModel,
    TelegramUserLinkModel,
)
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.schemas.telegram import (
    CreateLinkTokenRequest,
    CreateLinkTokenResponse,
    CreateTelegramLinkRequest,
    LinkTokenRead,
    TelegramInteractionRead,
    TelegramUserLinkRead,
    TelegramWebhookUpdate,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])

logger = logging.getLogger(__name__)

_session_store = SessionStore()

# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------

def get_orchestrator(session: Annotated[Session, Depends(get_db_session)]):  # noqa: ANN201
    from backend.app.application.reports.report_service import ReportService
    from backend.app.application.telegram.agent import ConversationalAgent
    from backend.app.application.telegram.bot_client import FakeBotClient, TelegramBotClient
    from backend.app.application.telegram.doctor_query_service import DoctorQueryService
    from backend.app.application.telegram.entity_resolver import EntityResolver
    from backend.app.application.telegram.intent_router import IntentRouter
    from backend.app.application.telegram.llm import DeepSeekProvider, FakeLLMProvider
    from backend.app.application.telegram.memory import MemoryManager
    from backend.app.application.telegram.orchestrator import TelegramOrchestrator
    from backend.app.application.telegram.query_executor import QueryExecutor
    from backend.app.application.telegram.tools import ToolGateway
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository
    from backend.app.infrastructure.repositories.telegram import TelegramRepository
    from backend.app.infrastructure.repositories.users import UserRepository

    use_real = settings.telegram_bot_token and settings.deepseek_api_key
    llm = DeepSeekProvider() if use_real else FakeLLMProvider()
    bot = TelegramBotClient() if settings.telegram_bot_token else FakeBotClient()

    query_executor = QueryExecutor(session, llm) if use_real else None
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    report_service = ReportService(
        calendar_repo=CalendarRepository(session),
        notification_repo=NotificationRepository(session),
        doctor_repo=DoctorRepository(session),
        mission_repo=MissionRepository(session),
        catalog_repo=CatalogRepository(session),
    )

    tools = ToolGateway(
        doctor_repo=DoctorRepository(session),
        calendar_repo=CalendarRepository(session),
        mission_repo=MissionRepository(session),
        availability_repo=AvailabilityRepository(session),
        query_executor=query_executor,
        report_service=report_service,
        catalog_repo=CatalogRepository(session),
    )
    router = IntentRouter()
    if session:
        router.set_session(session)

    memory = MemoryManager(TelegramRepository(session))
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=query_executor,
        tools=tools,
        memory=memory,
        session_store=_session_store,
        entity_resolver=EntityResolver(session=session),
        doctor_query_service=DoctorQueryService(session=session),
    )

    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(session),
        user_repo=UserRepository(session),
        agent=agent,
        bot_client=bot,
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
    chat_id: int | None = None
    telegram_user_id: str | None = None
    try:
        if update.message is None or update.message.text is None:
            return {"ok": True}

        if update.message.from_ is None:
            return {"ok": True}

        telegram_user_id = str(update.message.from_.id)
        telegram_username = update.message.from_.username
        chat_id = update.message.chat.id
        text = update.message.text

        # Attempt processing with 1 automatic retry on failure
        for attempt in range(2):
            try:
                orchestrator.handle_message(
                    telegram_user_id=telegram_user_id,
                    telegram_username=telegram_username,
                    chat_id=chat_id,
                    text=text,
                )
                break  # success → exit retry loop
            except Exception:
                if attempt == 0:
                    logger.warning(
                        "Webhook retry for user=%s chat=%s",
                        telegram_user_id, chat_id,
                    )
                    continue
                raise  # re-raise on second failure

        session.commit()
    except Exception:
        logger.exception(
            "Webhook error user=%s chat=%s",
            telegram_user_id or "?", chat_id or "?",
        )
        # Try to notify the user that something went wrong
        if chat_id is not None:
            orchestrator.send_error(
                chat_id,
                "Ocurrió un error al procesar tu mensaje. "
                "Intentá de nuevo en unos segundos.",
            )

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
# Link tokens (admin only)
# ---------------------------------------------------------------------------

@router.post(
    "/link-tokens",
    response_model=CreateLinkTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_link_token(
    payload: CreateLinkTokenRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CreateLinkTokenResponse:
    """Generate a single-use deep-link token for a user."""
    token_str = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)

    token_model = TelegramLinkTokenModel(
        id=str(uuid.uuid4()),
        token=token_str,
        user_id=payload.user_id,
        created_by=admin.id,
        created_at=now,
        expires_at=expires_at,
        active=True,
    )
    repo = TelegramRepository(session)
    repo.add_link_token(token_model)
    session.commit()

    bot_username = settings.telegram_bot_username
    deep_link_url = f"https://t.me/{bot_username}?start={token_str}"

    return CreateLinkTokenResponse(
        link_token=token_str,
        deep_link_url=deep_link_url,
        expires_at=expires_at,
    )


@router.get("/link-tokens", response_model=list[LinkTokenRead])
def list_link_tokens(
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[LinkTokenRead]:
    """List all generated link tokens."""
    repo = TelegramRepository(session)
    tokens = repo.list_link_tokens()
    return [LinkTokenRead.model_validate(t) for t in tokens]


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
