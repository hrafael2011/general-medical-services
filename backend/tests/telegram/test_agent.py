"""Tests for the refactored ConversationalAgent (LLM-first NLU)."""

import pytest

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_classifier import (
    ClassifiedIntent,
    IntentClassifier,
)
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


class StubIntentClassifier(IntentClassifier):
    """IntentClassifier stub that returns a predetermined ClassifiedIntent."""

    def __init__(self, intent: ClassifiedIntent | None = None) -> None:
        super().__init__(FakeLLMProvider())
        self._stub_intent = intent

    def classify(
        self,
        user_text: str,
        *,
        entity_hints: str = "",
        resolved_entities: dict | None = None,
    ) -> ClassifiedIntent:
        if self._stub_intent is not None:
            return self._stub_intent
        return ClassifiedIntent(domain="general", action="ambiguous", confidence=0.0)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _make_agent(
    llm: LLMProvider | None = None,
    router: IntentRouter | None = None,
    intent_classifier: IntentClassifier | None = None,
) -> ConversationalAgent:
    if llm is None:
        llm = FakeLLMProvider()
    if router is None:
        router = RouterStub()
    return ConversationalAgent(
        llm=llm,
        router=router,
        intent_classifier=intent_classifier,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_agent_constructor() -> None:
    """Agent can be constructed with minimal dependencies."""
    agent = _make_agent()
    assert agent._llm is not None
    assert agent._router is not None


def test_process_returns_agent_result() -> None:
    """process() always returns an AgentResult."""
    agent = _make_agent()
    result = agent.process(text="hola")
    assert isinstance(result, AgentResult)


# ---------------------------------------------------------------------------
# Intent classification routing tests
# ---------------------------------------------------------------------------


def test_reply_action_from_classifier() -> None:
    """When classifier returns action=reply, the response_text is used directly."""
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="general",
            action="reply",
            response_text="¡Hola! Soy el asistente de turnos medicos.",
        )
    )
    agent = _make_agent(intent_classifier=classifier)
    result = agent.process(text="hola")
    assert result.agent_action == "reply"
    assert "Hola" in result.response_text


def test_ambiguous_action_from_classifier() -> None:
    """When classifier returns action=ambiguous, clarification is requested."""
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="general",
            action="ambiguous",
            response_text="No entiendo tu consulta.",
        )
    )
    agent = _make_agent(intent_classifier=classifier)
    result = agent.process(text="asdfghjkl")
    assert result.agent_action == "ambiguous"
    assert result.response_text is not None


def test_query_type_routes_to_router() -> None:
    """When classifier returns a query_type, IntentRouter is called."""
    router = RouterStub()
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="medicos",
            action="query",
            query_type="doctors_by_rank",
            params={"rank": "sargento"},
        )
    )
    agent = _make_agent(router=router, intent_classifier=classifier)
    agent.process(text="muestrame los sargentos")
    assert router.last_handle_args is not None
    assert router.last_handle_args["query_type"] == "doctors_by_rank"
    assert router.last_handle_args["params"] == {"rank": "sargento"}


def test_export_action_routes_to_router_with_format() -> None:
    """When classifier returns action=export with format, router gets the format."""
    router = RouterStub()
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="medicos",
            action="export",
            query_type="list_active_doctors",
            params={},
            format="pdf",
        )
    )
    agent = _make_agent(router=router, intent_classifier=classifier)
    agent.process(text="dame un reporte PDF de los medicos")
    assert router.last_handle_args is not None
    assert router.last_handle_args["action"] == "export"
    assert router.last_handle_args["format"] == "pdf"


def test_export_without_format_uses_query_action() -> None:
    """When classifier returns action=export without format, router receives None format."""
    router = RouterStub()
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="medicos",
            action="export",
            query_type="list_active_doctors",
            params={},
        )
    )
    agent = _make_agent(router=router, intent_classifier=classifier)
    agent.process(text="exporta medicos")
    assert router.last_handle_args is not None
    assert router.last_handle_args.get("format") is None


def test_query_action_without_query_type_falls_back_to_ambiguous() -> None:
    """When classifier returns action=query but no query_type, and no services available,
    the agent asks for clarification."""
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="medicos",
            action="query",
            query_type=None,
            metric=None,
        )
    )
    agent = _make_agent(intent_classifier=classifier)
    result = agent.process(text="medicos")
    assert result.agent_action == "ambiguous"


def test_router_not_found_returns_fallback() -> None:
    """When router returns 'not found', agent returns fallback."""

    class RouterReturnsNotFound(IntentRouter):
        def handle(self, **kwargs) -> AgentResult:
            return AgentResult(
                response_text="No se encontro informacion sobre eso en el sistema."
            )

    router = RouterReturnsNotFound()
    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="medicos",
            action="query",
            query_type="count_doctors_total",
            params={},
        )
    )
    agent = ConversationalAgent(
        llm=FakeLLMProvider(),
        router=router,
        intent_classifier=classifier,
    )
    result = agent.process(text="consulta sin datos")
    assert isinstance(result, AgentResult)
    assert "encontr" in result.response_text.lower()


def test_memory_failure_is_handled_gracefully() -> None:
    """If memory.load_history() raises, agent continues without history."""

    class BrokenMemory:
        def load_history(self, telegram_user_id: str, limit: int = 10) -> list:
            raise RuntimeError("DB is down")

    classifier = StubIntentClassifier(
        ClassifiedIntent(
            domain="general",
            action="reply",
            response_text="Hola!",
        )
    )
    agent = ConversationalAgent(
        llm=FakeLLMProvider(),
        router=RouterStub(),
        memory=BrokenMemory(),  # type: ignore[arg-type]
        intent_classifier=classifier,
    )
    result = agent.process(text="hola", telegram_user_id="tg-123")
    assert isinstance(result, AgentResult)
    assert result.response_text is not None


def test_keyword_fallback_classifies_greeting() -> None:
    """Without IntentClassifier, the keyword fallback recognizes greetings."""
    agent = _make_agent()
    result = agent.process(text="hola buenos dias")
    assert result.agent_action == "reply"


def test_keyword_fallback_classifies_count_question() -> None:
    """Without IntentClassifier, the keyword fallback recognizes count questions."""
    agent = _make_agent()
    result = agent.process(text="cuantos medicos hay en total")
    assert result.agent_action == "ambiguous"  # No services wired, falls through


def test_keyword_fallback_defaults_to_ambiguous() -> None:
    """Without IntentClassifier, unrecognized text defaults to ambiguous."""
    agent = _make_agent()
    result = agent.process(text="xyzzy")
    assert result.agent_action == "ambiguous"


# ---------------------------------------------------------------------------
# _format_rows tests
# ---------------------------------------------------------------------------


def test_format_rows_empty() -> None:
    """0 filas → 'No se encontraron resultados.'"""
    from backend.app.application.telegram.agent import _format_rows
    assert _format_rows([], []) == "No se encontraron resultados."


def test_format_rows_single_row() -> None:
    """1 fila → muestra todos los campos con 'Resultado:'."""
    from backend.app.application.telegram.agent import _format_rows
    rows = [{"name": "Dr. Garcia", "count": 5}]
    result = _format_rows(rows, ["name", "count"])
    assert "Garcia" in result
    assert "Resultado:" in result


def test_format_rows_few_rows() -> None:
    """2-5 filas → lista numerada."""
    from backend.app.application.telegram.agent import _format_rows
    rows = [{"name": f"Dr. {i}", "sex": "M", "area": "E"} for i in range(3)]
    result = _format_rows(rows, ["name", "sex", "area"])
    assert "3 resultados" in result
    assert "1." in result
    assert "2." in result


def test_format_rows_many_rows() -> None:
    """Mas de 5 filas → muestra solo los primeros 5 con 'Los primeros'."""
    from backend.app.application.telegram.agent import _format_rows
    rows = [{"name": f"Dr. {i}"} for i in range(10)]
    result = _format_rows(rows, ["name"])
    assert "10 resultados" in result
    assert "Los primeros" in result
    assert "6." not in result
