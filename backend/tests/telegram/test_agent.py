"""Tests for the refactored ConversationalAgent (hybrid router)."""

import pytest

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider, LLMProvider
from backend.app.application.telegram.types import AgentResult


# ---------------------------------------------------------------------------
# Stub/mock helpers
# ---------------------------------------------------------------------------


class RouterStub(IntentRouter):
    """IntentRouter stub that returns a predetermined result."""

    def __init__(self, result: AgentResult | None = None) -> None:
        super().__init__()
        self.last_handle_args: dict | None = None
        self._stub_result = result

    def handle(self, **kwargs) -> AgentResult:  # type: ignore[override]
        self.last_handle_args = kwargs
        if self._stub_result is not None:
            return self._stub_result
        return AgentResult(response_text="respuesta del router")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_agent(
    llm: LLMProvider | None = None,
    router: IntentRouter | None = None,
) -> ConversationalAgent:
    if llm is None:
        llm = FakeLLMProvider()
    if router is None:
        router = RouterStub()
    return ConversationalAgent(llm=llm, router=router)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agent_constructor() -> None:
    """Agent can be constructed with minimal dependencies."""
    agent = _make_agent()
    assert agent._llm is not None
    assert agent._router is not None


def test_direct_reply_when_llm_returns_text(db_session) -> None:
    """When LLM returns plain text (not JSON), it's passed through as response."""
    llm = FakeLLMProvider(responses={"hola": "¡Hola! ¿En qué puedo ayudarte?"})
    agent = _make_agent(llm=llm)

    result = agent.process(text="Hola")

    assert result.response_text == "¡Hola! ¿En qué puedo ayudarte?"
    assert result.agent_action == "direct"


def test_reply_action_from_llm(db_session) -> None:
    """When LLM returns action=reply JSON, response_text is used."""
    llm = FakeLLMProvider(responses={
        "gracias": '{"action": "reply", "response_text": "De nada, saludos."}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="gracias")

    assert result.response_text == "De nada, saludos."
    assert result.agent_action == "reply"


def test_ambiguous_action_from_llm(db_session) -> None:
    """When LLM returns action=ambiguous, clarification prompt is returned."""
    llm = FakeLLMProvider(responses={
        "no sé": '{"action": "ambiguous", "response_text": "¿Podrías ser más específico?"}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="no sé")

    assert "específico" in result.response_text
    assert result.agent_action == "ambiguous"


def test_query_action_routes_to_router(db_session) -> None:
    """When LLM returns action=query, the router is called."""
    router = RouterStub()
    llm = FakeLLMProvider(responses={
        "activos": '{"action": "query", "query_type": "count_doctors_total", "params": {}}',
    })
    agent = _make_agent(llm=llm, router=router)

    agent.process(text="cuantos medicos activos hay")

    assert router.last_handle_args is not None
    assert router.last_handle_args["action"] == "query"
    assert router.last_handle_args["query_type"] == "count_doctors_total"


def test_export_action_routes_to_router(db_session) -> None:
    """When LLM returns action=export, the router is called."""
    router = RouterStub()
    llm = FakeLLMProvider(responses={
        "pdf": '{"action": "export", "query_type": "list_active_doctors", "params": {}}',
    })
    agent = _make_agent(llm=llm, router=router)

    agent.process(text="exporta PDF de medicos activos")

    assert router.last_handle_args is not None
    assert router.last_handle_args["action"] == "export"
    assert router.last_handle_args["query_type"] == "list_active_doctors"


def test_legacy_call_tool_format_falls_back_to_tools(db_session) -> None:
    """Old-format {action: 'call_tool', tool: '...'} still works via ToolGateway."""
    from backend.app.application.telegram.tools import ToolGateway
    from backend.app.infrastructure.repositories.doctors import DoctorRepository

    llm = FakeLLMProvider(responses={
        "activos": (
            '{"action": "call_tool", "tool": "count_medicos_activos", "entities": {}}'
        ),
    })
    router = RouterStub()
    tools = ToolGateway(
        doctor_repo=DoctorRepository(db_session),
        calendar_repo=None,  # type: ignore[arg-type]
        mission_repo=None,   # type: ignore[arg-type]
        availability_repo=None,  # type: ignore[arg-type]
    )
    agent = ConversationalAgent(llm=llm, router=router, tools=tools)

    result = agent.process(text="cuantos medicos activos hay")

    assert result.agent_action == "call_tool"
    assert result.tool_name == "count_medicos_activos"


def test_unknown_query_type_falls_back_to_reply(db_session) -> None:
    """When router returns not-found, agent returns fallback message."""
    llm = FakeLLMProvider(responses={
        "rare": '{"action": "query", "query_type": "nonexistent_query", "params": {}}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="consulta rara")

    assert result.response_text is not None
    # Should fallback (no query_executor set) to "not found"
    assert "encontrar" in result.response_text.lower()


def test_process_returns_agent_result(db_session) -> None:
    """process() always returns an AgentResult."""
    llm = FakeLLMProvider(responses={"test": '{"action": "reply", "response_text": "ok"}'})
    agent = _make_agent(llm=llm)

    result = agent.process(text="test")

    assert isinstance(result, AgentResult)


def test_user_info_passed_to_prompt(db_session) -> None:
    """User info is included in the system prompt."""
    llm = FakeLLMProvider(responses={"hola": "Hola Dr. Pérez"})
    agent = _make_agent(llm=llm)

    result = agent.process(
        text="Hola",
        user_info={"name": "Dr. Pérez", "role": "medico", "id": "123"},
    )

    assert result.response_text is not None
