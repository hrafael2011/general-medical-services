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


def test_agent_routes_monthly_assigned_doctor_count_without_llm() -> None:
    """Preguntas claras de asignaciones mensuales usan consulta segura registrada."""
    llm = FakeLLMProvider(responses={
        "cuantos medicos fueron asignados para servicios en junio 2026": (
            '{"action": "query", "query_type": "list_active_doctors", "params": {}}'
        )
    })
    router = RouterStub(result=AgentResult(response_text="Resultado: total: 76", agent_action="query"))
    agent = ConversationalAgent(llm=llm, router=router)

    result = agent.process(
        text="cuantos medicos fueron asignados para servicios en junio 2026"
    )

    assert result.response_text == "Resultado: total: 76"
    assert router.last_handle_args is not None
    assert router.last_handle_args["query_type"] == "count_assigned_doctors_by_month"
    assert router.last_handle_args["params"] == {"month": 6, "year": 2026}
    assert llm.calls == []


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
        "rara": '{"action": "query", "query_type": "nonexistent_query", "params": {}}',
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


# ---------------------------------------------------------------------------
# _extract_json tests
# ---------------------------------------------------------------------------


def test_extract_json_plain_object() -> None:
    """JSON puro sin markdown es parseado correctamente."""
    result = ConversationalAgent._extract_json('{"action": "reply", "response_text": "ok"}')
    assert result == {"action": "reply", "response_text": "ok"}


def test_extract_json_markdown_code_block() -> None:
    """JSON dentro de bloque ```json ... ``` es extraído."""
    text = '```json\n{"action": "query", "query_type": "count_doctors_total"}\n```'
    result = ConversationalAgent._extract_json(text)
    assert result is not None
    assert result["action"] == "query"


def test_extract_json_invalid_returns_none() -> None:
    """Texto no-JSON devuelve None."""
    assert ConversationalAgent._extract_json("Hola, soy un asistente.") is None


def test_extract_json_partial_json_returns_none() -> None:
    """JSON incompleto devuelve None."""
    assert ConversationalAgent._extract_json('{"action": "reply"') is None


# ---------------------------------------------------------------------------
# _format_rows tests (función en agent.py)
# ---------------------------------------------------------------------------


def test_format_rows_empty() -> None:
    """0 filas → 'No se encontraron resultados.'"""
    from backend.app.application.telegram.agent import _format_rows
    assert _format_rows([], []) == "No se encontraron resultados."


def test_format_rows_single_row() -> None:
    """1 fila → muestra todos los campos con 'Resultado:'."""
    from backend.app.application.telegram.agent import _format_rows
    rows = [{"name": "Dr. García", "count": 5}]
    result = _format_rows(rows, ["name", "count"])
    assert "García" in result
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
    """Más de 5 filas → muestra solo los primeros 5 con 'Los primeros'."""
    from backend.app.application.telegram.agent import _format_rows
    rows = [{"name": f"Dr. {i}"} for i in range(10)]
    result = _format_rows(rows, ["name"])
    assert "10 resultados" in result
    assert "Los primeros" in result
    assert "6." not in result


# ---------------------------------------------------------------------------
# Fallbacks y edge cases del agente
# ---------------------------------------------------------------------------


def test_export_without_query_type_returns_fallback(db_session) -> None:
    """action=export sin query_type → no explota, devuelve AgentResult."""
    llm = FakeLLMProvider(responses={
        "exporta": '{"action": "export", "query_type": "", "params": {}}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="exporta algo")

    assert isinstance(result, AgentResult)
    assert result.response_text is not None


def test_unknown_action_from_llm_returns_fallback(db_session) -> None:
    """LLM devuelve action desconocida → AgentResult con mensaje genérico."""
    llm = FakeLLMProvider(responses={
        "algo": '{"action": "teleport", "query_type": "", "params": {}}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="algo extraño")

    assert isinstance(result, AgentResult)
    assert result.response_text is not None
    assert len(result.response_text) > 0


def test_agent_validates_llm_output_with_pydantic(db_session) -> None:
    """LLM output with action='invalid_action' → validation error, graceful fallback."""
    llm = FakeLLMProvider(responses={
        "mal": '{"action": "invalid_action", "query_type": "", "params": {}}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="mal")

    assert result.agent_action == "validation_error"
    assert result.response_text is not None


def test_agent_low_confidence_returns_clarification(db_session) -> None:
    """confidence < 0.6 → ambiguous response asking for clarification."""
    llm = FakeLLMProvider(responses={
        "duda": '{"action": "query", "query_type": "count_doctors_total", "confidence": 0.3}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="duda")

    assert result.agent_action == "ambiguous"
    assert "específico" in result.response_text.lower()


def test_agent_missing_fields_triggers_prompt(db_session) -> None:
    """missing_fields not empty → agent asks for the missing info."""
    llm = FakeLLMProvider(responses={
        "faltante": '{"action": "query", "query_type": "doctors_by_sex", '
                    '"missing_fields": ["sex"], "confidence": 0.75}',
    })
    agent = _make_agent(llm=llm)

    result = agent.process(text="faltante")

    assert result.agent_action == "ambiguous"
    assert "sex" in result.response_text.lower()


def test_router_not_found_triggers_fallback_to_no_results(db_session) -> None:
    """Router devuelve 'No pude encontrar...' → agente hace fallback (sin query_executor → mensaje genérico)."""

    class RouterReturnsNotFound(IntentRouter):
        def handle(self, **kwargs) -> AgentResult:
            return AgentResult(response_text="No pude encontrar información sobre eso en el sistema.")

    llm = FakeLLMProvider(responses={
        "consulta": '{"action": "query", "query_type": "alguna_consulta", "params": {}}',
    })
    router = RouterReturnsNotFound()
    agent = ConversationalAgent(llm=llm, router=router, query_executor=None)

    result = agent.process(text="consulta sin datos")

    assert isinstance(result, AgentResult)
    assert "encontrar" in result.response_text.lower()


def test_agent_uses_entity_hints_in_prompt(db_session) -> None:
    """EntityResolver hints are included in the system prompt."""
    from backend.app.application.telegram.entity_resolver import EntityResolver

    llm = FakeLLMProvider(responses={
        "Pérez": '{"action": "query", "query_type": "doctor_detail", "params": {"search": "Pérez"}}',
    })
    router = RouterStub()
    resolver = EntityResolver(session=None)
    agent = ConversationalAgent(llm=llm, router=router, entity_resolver=resolver)

    agent.process(text="busca a Pérez")

    assert llm.calls
    call_text = " ".join(m.get("content", "") for m in llm.calls[-1].get("messages", []))


def test_memory_failure_is_handled_gracefully(db_session) -> None:
    """Si memory.load_history() lanza excepción, el agente continúa sin history."""

    class BrokenMemory:
        def load_history(self, telegram_user_id: str, limit: int = 10) -> list:
            raise RuntimeError("DB is down")

    llm = FakeLLMProvider(responses={"hola": '{"action": "reply", "response_text": "Hola!"}'})
    agent = ConversationalAgent(llm=llm, router=RouterStub(), memory=BrokenMemory())  # type: ignore[arg-type]

    result = agent.process(text="hola", telegram_user_id="tg-123")

    assert isinstance(result, AgentResult)
    assert result.response_text is not None


# ---------------------------------------------------------------------------
# M5: Export format tests
# ---------------------------------------------------------------------------


def test_export_excel_format_reaches_router(db_session) -> None:
    """Cuando el LLM devuelve format=excel, el router recibe ese format."""
    router = RouterStub()
    llm = FakeLLMProvider(responses={
        "excel": '{"action": "export", "query_type": "list_active_doctors", "params": {}, "format": "excel"}',
    })
    agent = _make_agent(llm=llm, router=router)
    agent.process(text="dame un excel de los médicos activos")
    assert router.last_handle_args is not None
    assert router.last_handle_args.get("format") == "excel"


def test_export_pdf_is_default_format(db_session) -> None:
    """Cuando el LLM no especifica format, el router lo recibe como None (PDF default)."""
    router = RouterStub()
    llm = FakeLLMProvider(responses={
        "exporta médicos activos": '{"action": "export", "query_type": "list_active_doctors", "params": {}}',
    })
    agent = _make_agent(llm=llm, router=router)
    agent.process(text="exporta médicos activos")
    assert router.last_handle_args is not None
    assert router.last_handle_args.get("format") is None


def test_export_falls_back_to_query_executor(db_session) -> None:
    """Cuando el query_type no existe y action=export, debe hacer fallback a QueryExecutor."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    doc = DoctorModel(
        id=str(_uuid.uuid4()),
        name="Dr. ExportFallback",
        normalized_name="dr. exportfallback",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="variable",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        rank_id=None,
        department_id=None,
        created_at=_dt.now(UTC),
        updated_at=_dt.now(UTC),
    )
    db_session.add(doc)
    db_session.flush()

    class StubQueryExecutor:
        def execute(self, nl_query: str, user_text: str = "", entity_hints: str = "") -> dict:
            # Return >20 rows so _format_nl_response falls back to _format_rows
            # (avoids the FakeLLMProvider not supporting NL formatting in tests)
            rows = [{"name": f"Dr. ExportFallback {i}"} for i in range(25)]
            return {
                "ok": True,
                "data": {
                    "columns": ["name"],
                    "rows": rows,
                    "row_count": 25,
                    "truncated": False,
                },
            }

    router = RouterStub(
        result=AgentResult(response_text="No pude encontrar información sobre eso en el sistema.")
    )
    llm = FakeLLMProvider(responses={
        "exporta": (
            '{"action": "export", "query_type": "nonexistent_export_query", "params": {}}'
        ),
    })
    agent = ConversationalAgent(llm=llm, router=router, query_executor=StubQueryExecutor())

    result = agent.process(text="exporta un reporte de algo no registrado")

    assert "ExportFallback" in result.response_text
    assert result.agent_action == "query_db"
