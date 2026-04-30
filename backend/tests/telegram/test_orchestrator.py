"""
DB-backed integration tests for TelegramOrchestrator.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.infrastructure.db.models.telegram import TelegramUserLinkModel, TelegramInteractionModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.application.telegram.orchestrator import TelegramOrchestrator
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.bot_client import FakeBotClient

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class StubClassifier:
    def __init__(self, intent: str, entities: dict, confidence: float):
        self._response = {"intent": intent, "entities": entities, "confidence": confidence}

    def classify(self, text: str) -> dict:
        return self._response


class StubTools:
    def __init__(self, response: dict):
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    def execute(self, intent: str, entities: dict) -> dict:
        self.calls.append((intent, entities))
        return self._response


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _new_user(
    db_session,
    *,
    active: bool = True,
    must_change_password: bool = False,
    role: str = "encargado",
) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Test User",
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=active,
        password_hash="hashed",
        must_change_password=must_change_password,
        token_version=1,
        failed_login_count=0,
        locked_until=None,
        last_login_at=None,
        password_changed_at=None,
        created_by=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _new_link(db_session, *, user_id: str, telegram_user_id: str, active: bool = True) -> TelegramUserLinkModel:
    link = TelegramUserLinkModel(
        id=str(uuid.uuid4()),
        telegram_user_id=telegram_user_id,
        telegram_username="testuser",
        user_id=user_id,
        active=active,
        linked_by=None,
        linked_at=datetime.now(UTC),
        last_used_at=None,
    )
    db_session.add(link)
    db_session.flush()
    return link


def _make_orchestrator(
    db_session,
    *,
    classifier=None,
    tools=None,
    bot_client=None,
    llm=None,
) -> TelegramOrchestrator:
    if classifier is None:
        classifier = StubClassifier("out_of_domain", {}, 0.9)
    if tools is None:
        tools = StubTools({"ok": False, "error": "out_of_domain"})
    if bot_client is None:
        bot_client = FakeBotClient()
    if llm is None:
        llm = FakeLLMProvider()
    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(db_session),
        user_repo=UserRepository(db_session),
        classifier=classifier,
        tools=tools,
        bot_client=bot_client,
        llm=llm,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_unlinked_user_returns_not_linked(db_session) -> None:
    """A telegram_user_id with no active link should get the 'not linked' message."""
    orchestrator = _make_orchestrator(db_session)

    response = orchestrator.handle_message(
        telegram_user_id="unknown-tg-id",
        telegram_username="stranger",
        chat_id=12345,
        text="Hola",
    )

    assert "No estás vinculado" in response


def test_linked_inactive_user_blocked(db_session) -> None:
    """A linked but inactive system user should be blocked with an 'inactiva' message."""
    user = _new_user(db_session, active=False)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    orchestrator = _make_orchestrator(db_session)
    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="inactiveuser",
        chat_id=11111,
        text="¿Cuántos médicos hay?",
    )

    assert "inactiva" in response


def test_must_change_password_blocked(db_session) -> None:
    """Active user who must change password should be told to change their 'contraseña'."""
    user = _new_user(db_session, active=True, must_change_password=True)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    orchestrator = _make_orchestrator(db_session)
    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="mustchangeuser",
        chat_id=22222,
        text="Lista médicos",
    )

    assert "contraseña" in response


def test_out_of_domain_intent(db_session) -> None:
    """A message classified as out_of_domain should return the out-of-scope message."""
    user = _new_user(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    classifier = StubClassifier("out_of_domain", {}, 0.9)
    orchestrator = _make_orchestrator(db_session, classifier=classifier)

    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="regularuser",
        chat_id=33333,
        text="Cuéntame un chiste",
    )

    assert "fuera del alcance" in response


def test_count_medicos_activos_happy_path(db_session) -> None:
    """count_medicos_activos intent with a stub that returns count=3 should have '3' in response."""
    user = _new_user(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    classifier = StubClassifier("count_medicos_activos", {}, 0.9)
    tools = StubTools({"ok": True, "data": {"count": 3}})
    orchestrator = _make_orchestrator(db_session, classifier=classifier, tools=tools)

    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="regularuser",
        chat_id=44444,
        text="¿Cuántos médicos activos hay?",
    )

    assert "3" in response
    assert len(tools.calls) == 1
    assert tools.calls[0][0] == "count_medicos_activos"


def test_interaction_is_logged(db_session) -> None:
    """Every message (even unlinked) must create a TelegramInteractionModel in the DB."""
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    orchestrator = _make_orchestrator(db_session)

    orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="anyone",
        chat_id=55555,
        text="Test message",
    )

    stmt = select(TelegramInteractionModel).where(
        TelegramInteractionModel.telegram_user_id == tg_id
    )
    interactions = list(db_session.scalars(stmt))
    assert len(interactions) == 1
    assert interactions[0].input_text == "Test message"
