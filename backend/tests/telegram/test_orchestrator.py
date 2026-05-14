"""
DB-backed integration tests for TelegramOrchestrator.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.application.telegram.bot_client import FakeBotClient
from backend.app.application.telegram.orchestrator import TelegramOrchestrator
from backend.app.application.telegram.types import AgentResult
from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramUserLinkModel,
)
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository

UTC = UTC


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class StubAgent:
    """Returns a predetermined AgentResult for testing orchestrator flow."""

    def __init__(self, result: AgentResult) -> None:
        self._result = result
        self.calls: list[dict] = []

    def process(
        self,
        text: str,
        telegram_user_id: str | None = None,
        user_info: dict | None = None,
        actor_id: str | None = None,
    ) -> AgentResult:
        self.calls.append({
            "text": text,
            "telegram_user_id": telegram_user_id,
            "user_info": user_info,
            "actor_id": actor_id,
        })
        return self._result


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


def _new_link(
    db_session,
    *,
    user_id: str,
    telegram_user_id: str,
    active: bool = True,
) -> TelegramUserLinkModel:
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
    agent=None,
    bot_client=None,
) -> TelegramOrchestrator:
    if agent is None:
        agent = StubAgent(AgentResult(response_text="Respuesta por defecto"))
    if bot_client is None:
        bot_client = FakeBotClient()
    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(db_session),
        user_repo=UserRepository(db_session),
        agent=agent,
        bot_client=bot_client,
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


def test_agent_response_passed_through(db_session) -> None:
    """The orchestrator should pass through whatever the agent returns."""
    user = _new_user(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    agent = StubAgent(AgentResult(response_text="Respuesta personalizada"))
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="regularuser",
        chat_id=33333,
        text="Cuéntame un chiste",
    )

    assert response == "Respuesta personalizada"


def test_agent_tool_response_with_data(db_session) -> None:
    """Tool result metadata in AgentResult should be logged but response text comes through."""
    user = _new_user(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    agent = StubAgent(AgentResult(
        response_text="Hay 3 medicos activos.",
        agent_action="call_tool",
        tool_name="count_medicos_activos",
        tool_entities={},
        tool_result={"ok": True, "data": {"count": 3}},
    ))
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="regularuser",
        chat_id=44444,
        text="¿Cuántos médicos activos hay?",
    )

    assert "3" in response
    assert len(agent.calls) == 1
    assert agent.calls[0]["text"] == "¿Cuántos médicos activos hay?"
    assert agent.calls[0]["user_info"]["name"] == "Test User"


def test_agent_receives_user_info(db_session) -> None:
    """The agent should receive user info (name, role, id) from the orchestrator."""
    user = _new_user(db_session, role="encargado")
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)

    agent = StubAgent(AgentResult(response_text="OK"))
    orchestrator = _make_orchestrator(db_session, agent=agent)

    orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="docuser",
        chat_id=55555,
        text="Mi historial",
    )

    assert len(agent.calls) == 1
    info = agent.calls[0]["user_info"]
    assert info["name"] == "Test User"
    assert info["role"] == "encargado"
    assert info["id"] == user.id


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


def test_confirmation_command_is_blocked_for_internal_users(db_session) -> None:
    user = _new_user(db_session, role="encargado")
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    _new_link(db_session, user_id=user.id, telegram_user_id=tg_id)
    agent = StubAgent(AgentResult(response_text="No debe llamarse"))
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=tg_id,
        telegram_username="docuser",
        chat_id=99999,
        text="/confirmar token-de-prueba",
    )

    assert "cuentas internas" in response
    assert agent.calls == []
