"""Telegram webhook and user-link management routes."""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_admin
from backend.app.core.config import settings
from backend.app.infrastructure.rate_limiter import RateLimiter
from backend.app.infrastructure.db.models.telegram import (
    TelegramLinkTokenModel,
    TelegramUserLinkModel,
)
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository
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

_warned_no_webhook_secret = False

_TELEGRAM_LINKABLE_ROLES = {"admin", "encargado"}

# Per-user rate limiter for the Telegram webhook:
# 20 requests/minute per telegram_user_id
_webhook_limiter = RateLimiter(max_requests=20, window_seconds=60)


# ---------------------------------------------------------------------------
# Compatibility aliases for old rate limiter API (used by tests)
# ---------------------------------------------------------------------------

_RATE_LIMIT_BUCKET: dict[str, list[float]] = {}


def _is_rate_limited(key: str, limit_per_minute: int = 20, now=None) -> bool:
    if now is None:
        now = datetime.now(UTC)
    cutoff = now.timestamp() - 60
    bucket = _RATE_LIMIT_BUCKET.setdefault(key, [])
    _RATE_LIMIT_BUCKET[key] = [t for t in bucket if t > cutoff]
    bucket = _RATE_LIMIT_BUCKET[key]
    if len(bucket) >= limit_per_minute:
        return True
    bucket.append(now.timestamp())
    return False


def _build_rate_limited_tool_response() -> dict:
    return {
        "ok": True,
        "observability": {
            "action": "discarded",
            "route": "webhook_rate_limit",
            "fallback_reason": "rate_limited",
            "has_document": False,
        },
    }


def _get_linkable_user(session: Session, user_id: str) -> UserModel:
    user = UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    if user.role not in _TELEGRAM_LINKABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo usuarios admin y encargado pueden vincularse a Telegram.",
        )
    return user

# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------

def get_orchestrator(session: Annotated[Session, Depends(get_db_session)]):  # noqa: ANN201
    from backend.app.application.telegram.agent import ConversationalAgent
    from backend.app.application.telegram.bot_client import FakeBotClient, TelegramBotClient
    from backend.app.application.telegram.calendar_query_service import CalendarQueryService
    from backend.app.application.telegram.doctor_query_service import DoctorQueryService
    from backend.app.application.telegram.entity_resolver import EntityResolver
    from backend.app.application.telegram.intent_classifier import (
        IntentClassifier,
        NLUEngine,
    )
    from backend.app.application.telegram.intent_router import IntentRouter
    from backend.app.application.telegram.llm import DeepSeekProvider, FakeLLMProvider
    from backend.app.application.telegram.memory import MemoryManager, SessionStore
    from backend.app.application.telegram.orchestrator import TelegramOrchestrator
    from backend.app.application.telegram.query_executor import QueryExecutor
    from backend.app.application.telegram.semantic_layer import SemanticLayerResolver
    from backend.app.application.telegram.tool_registry import ToolRegistry
    from backend.app.application.reports.report_service import ReportService
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository
    from backend.app.infrastructure.repositories.telegram import TelegramRepository
    from backend.app.infrastructure.repositories.users import UserRepository

    use_real = settings.telegram_bot_token and settings.deepseek_api_key
    llm = DeepSeekProvider() if use_real else FakeLLMProvider()
    bot = TelegramBotClient() if settings.telegram_bot_token else FakeBotClient()

    query_executor = QueryExecutor(session, llm) if use_real else None
    router = IntentRouter()
    if session:
        router.set_session(session)

    intent_classifier = IntentClassifier(llm) if use_real else None
    nlu_engine = NLUEngine(llm) if use_real else None

    doctor_svc = DoctorQueryService(session=session)
    calendar_svc = CalendarQueryService(session=session)
    entity_resolver = EntityResolver(session=session)
    semantic_layer = SemanticLayerResolver(session)

    # Wire tool registry with deterministic handlers
    tool_registry = ToolRegistry()
    if use_real:

        def _doctor_handler(**params):
            resolved = entity_resolver.pre_process(
                " ".join(f"{k}={v}" for k, v in params.items())
            ).get("resolved", params)
            return doctor_svc.execute(
                " ".join(f"{k}={v}" for k, v in params.items()),
                resolved,
            )

        tool_registry.register("list_doctors", _doctor_handler)
        tool_registry.register("count_doctors", _doctor_handler)
        tool_registry.register("doctors_by_sex", _doctor_handler)
        tool_registry.register("doctors_by_rank", _doctor_handler)
        tool_registry.register("doctors_by_department", _doctor_handler)

        tool_registry.register(
            "calendar_assignments",
            lambda **params: calendar_svc.execute("list_calendar_assignments_by_date_range", params),
        )
        tool_registry.register(
            "calendar_assigned_count",
            lambda **params: calendar_svc.execute("count_assigned_doctors_by_month", params),
        )
        tool_registry.register(
            "calendar_status",
            lambda **params: calendar_svc.execute("calendar_status", params),
        )

        # Mission tools — route through IntentRouter (prevents SQL Agent fallback)
        def _mission_list_handler(**params):
            result = router.handle(
                action="query",
                query_type="list_active_missions",
                params=params,
            )
            return result

        def _mission_status_handler(**params):
            result = router.handle(
                action="query",
                query_type="pending_mission_confirmation",
                params=params,
            )
            return result

        tool_registry.register("mission_list", _mission_list_handler)
        tool_registry.register("mission_status", _mission_status_handler)

        def _sql_handler(**params):
            result = query_executor.execute(
                nl_query=params.get("question", ""),
                user_text=params.get("question", ""),
            )
            return result

        tool_registry.register("sql_query", _sql_handler)

    memory = MemoryManager(TelegramRepository(session))
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=query_executor,
        memory=memory,
        session_store=SessionStore(ttl_seconds=1800, telegram_repo=TelegramRepository(session)),
        entity_resolver=entity_resolver,
        doctor_query_service=doctor_svc,
        calendar_query_service=calendar_svc,
        semantic_layer_resolver=semantic_layer,
        intent_classifier=intent_classifier,
        nlu_engine=nlu_engine,
        tool_registry=tool_registry,
    )

    # Create ReportService for report generation
    calendar_repo = CalendarRepository(session)
    notification_repo = NotificationRepository(session)
    doctor_repo = DoctorRepository(session)
    mission_repo = MissionRepository(session)
    catalog_repo = CatalogRepository(session)
    report_service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=notification_repo,
        doctor_repo=doctor_repo,
        mission_repo=mission_repo,
        catalog_repo=catalog_repo,
    )

    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(session),
        user_repo=UserRepository(session),
        agent=agent,
        bot_client=bot,
        report_service=report_service,
        nlu_engine=nlu_engine,
    )


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@router.get("/webhook")
def webhook_verify(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> str:
    """Handle Telegram webhook verification GET request."""
    secret = settings.telegram_webhook_secret
    if hub_mode == "subscribe" and secret and hub_verify_token == secret:
        return hub_challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/webhook", status_code=200)
def webhook(
    update: TelegramWebhookUpdate,
    session: Annotated[Session, Depends(get_db_session)],
    orchestrator: Annotated[object, Depends(get_orchestrator)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict:
    """Telegram Bot API webhook. Always returns 200 to avoid Telegram retries."""
    # Kill switch — disable bot globally via FEATURE_TELEGRAM env var
    if not settings.feature_telegram:
        return {"ok": True, "status": "bot_disabled"}

    # Validate X-Telegram-Bot-Api-Secret-Token if configured
    secret = settings.telegram_webhook_secret
    if secret is not None:
        if x_telegram_bot_api_secret_token is None or not secrets.compare_digest(
            x_telegram_bot_api_secret_token, secret
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    else:
        global _warned_no_webhook_secret
        if not _warned_no_webhook_secret:
            logger.warning("TELEGRAM_WEBHOOK_SECRET is not configured — webhook is unauthenticated")
            _warned_no_webhook_secret = True

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

        # Rate limiting: 20 req/min per user
        if not _webhook_limiter.allow(telegram_user_id):
            logger.warning(
                "Rate limited user=%s chat=%s",
                telegram_user_id, chat_id,
            )
            return {"ok": True, "rate_limited": True}

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
                session.rollback()
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
    _get_linkable_user(session, payload.user_id)
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
    _get_linkable_user(session, payload.user_id)
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
