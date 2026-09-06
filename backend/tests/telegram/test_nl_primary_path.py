"""Tests del fallback SQL interno del path enrutado (2026-09-05).

El intent legacy `query_db` ya no existe como path público: el agente
clasifica con NLUEngine y despacha tools del catálogo MCP; el SQL Agent es
un fallback interno y silencioso de `_dispatch_tool` cuando una tool no
tiene handler cableado (spec 15: `sql_query` no está en el catálogo ni en
el prompt). Estos tests ejercitan ese fallback a través del pipeline
LLM-first y verifican que la respuesta final queda anclada a datos reales.

El reenvío de entity hints al QueryExecutor se eliminó: la extracción de
entidades ocurre dentro del LLM (params del NLU). EntityResolver sigue
cubierto por test_entity_resolver.py.
"""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_classifier import NLUEngine
from backend.app.application.telegram.intent_router import IntentRouter


class FakeLLMForNL:
    """LLM por fases: JSON del NLU en clasificación; texto formateado en 0.3."""

    name = "fake-nl"

    def __init__(self, intent_json="", format_response=""):
        self.intent_json = intent_json or (
            '{"tool": "list_doctors", "params": {}, '
            '"confidence": 1.0, "needs_clarification": false}'
        )
        self.format_response = format_response
        self.calls = []

    def chat_complete(self, messages, temperature=0.0, json_mode=False):
        self.calls.append({"temperature": temperature, "json_mode": json_mode})
        if temperature == 0.3:
            return self.format_response
        if json_mode or temperature == 0.0:
            return self.intent_json
        return ""


class FakeQueryExecutor:
    def __init__(self, rows=None, columns=None, ok=True):
        self.rows = rows or []
        self.columns = columns or []
        self.ok = ok
        self.last_entity_hints = None

    def execute(self, nl_query, user_text="", entity_hints=""):
        self.last_entity_hints = entity_hints
        if not self.ok:
            return {"ok": False, "error": "test error"}
        return {
            "ok": True,
            "data": {
                "columns": self.columns,
                "rows": self.rows,
                "row_count": len(self.rows),
                "truncated": False,
                "elapsed_seconds": 0.1,
            },
        }


def _make_agent(llm, query_executor) -> ConversationalAgent:
    """Agente LLM-first sin handlers cableados: la tool cae al fallback SQL."""
    return ConversationalAgent(
        llm=llm,
        # IntentRouter() registra los DEFAULT_QUERY_TYPES; list_doctors no está
        # entre ellos → el dispatch cae al fallback interno del SQL Agent.
        router=IntentRouter(),
        query_executor=query_executor,
        nlu_engine=NLUEngine(llm),
    )


def test_tool_sin_handler_cae_al_fallback_sql_interno():
    """Tool del catálogo sin handler cableado → fallback SQL interno con datos."""
    llm = FakeLLMForNL(
        intent_json='{"tool": "list_doctors", "params": {"count": true}, "confidence": 1.0}',
        format_response="Tienes 15 medicos masculinos en el sistema.",
    )
    qe = FakeQueryExecutor(rows=[{"total": 15}], columns=["total"])
    agent = _make_agent(llm, qe)

    result = agent.process("cuantos medicos masculinos hay")

    assert result.agent_action == "query"
    assert result.tool_name == "list_doctors"
    assert "15" in result.response_text
    # El fallback SQL quedó registrado como origen interno del resultado.
    assert result.tool_result is not None
    assert result.tool_result.get("agent_action") == "query_db"


def test_fallback_sql_con_error_devuelve_respuesta_controlada():
    """QueryExecutor falla → respuesta controlada, sin excepción."""
    llm = FakeLLMForNL(
        intent_json='{"tool": "list_doctors", "params": {"count": true}, "confidence": 1.0}',
        format_response="",
    )
    qe = FakeQueryExecutor(rows=[{"total": 8}], columns=["total"], ok=False)
    agent = _make_agent(llm, qe)

    result = agent.process("cuantos medicos masculinos hay")

    assert "No pude encontrar" in result.response_text
    assert result.tool_result is not None
    assert result.tool_result.get("agent_action") == "query_db"


def test_fallback_sql_sin_datos_formatea_explicacion_natural():
    """QueryExecutor sin filas → explicación natural guionada por el LLM."""
    llm = FakeLLMForNL(
        intent_json='{"tool": "list_doctors", "params": {}, "confidence": 1.0}',
        format_response="No encontre ningun medico con ese nombre en la base de datos.",
    )
    qe = FakeQueryExecutor(rows=[], columns=["id", "name"])
    agent = _make_agent(llm, qe)

    result = agent.process("busca al doctor masculino xyz")

    assert "No encontre" in result.response_text
    assert result.tool_result is not None
    assert result.tool_result.get("agent_action") == "query_db"
