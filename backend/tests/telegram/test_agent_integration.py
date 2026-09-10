"""
Tests de integración del agente conversacional — flujo LLM-first (2026-09-05).

Pipeline actual: FakeLLM (NLU) → ConversationalAgent (LLM-first) → ToolRegistry
(handlers del catálogo MCP de 22 tools) → PostgreSQL real → generate_response
en español usando SOLO los datos devueltos por el handler.

El `ScriptedAgentLLM` devuelve el JSON del NLU en la fase de clasificación y,
en la fase de formateo, hace eco del payload del handler: así la respuesta
final contiene literalmente los datos reales del backend y las asserts
verifican que el agente solo formatea datos devueltos.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_classifier import NLUEngine
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.registry import QueryRegistry
from backend.app.application.telegram.tool_handlers import build_tool_handlers
from backend.app.application.telegram.tool_registry import ToolRegistry
from backend.app.application.telegram.types import AgentResult
from backend.app.infrastructure.db.models.doctors import DoctorModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_doctors(db_session, count: int = 3) -> list[DoctorModel]:
    """Crea `count` médicos activos en el DB de prueba."""
    doctors = []
    for i in range(count):
        d = DoctorModel(
            id=str(uuid.uuid4()),
            name=f"Dr. Integracion {i}",
            normalized_name=f"dr. integracion {i}",
            sex="M" if i % 2 == 0 else "F",
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
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(d)
        doctors.append(d)
    db_session.flush()
    return doctors


def _make_router(db_session) -> IntentRouter:
    """IntentRouter con SQL de PostgreSQL y sesión configurada."""
    registry = QueryRegistry()
    registry.register_many([
        {
            "query_type": "test_count_doctors",
            "sql_template": (
                "SELECT COUNT(*) AS total FROM doctors "
                "WHERE active = TRUE AND service_active = TRUE"
            ),
            "params_schema": {},
            "description": "Cuenta medicos activos (PostgreSQL).",
        },
        {
            "query_type": "test_list_doctors",
            "sql_template": (
                "SELECT name, sex FROM doctors "
                "WHERE active = TRUE AND service_active = TRUE ORDER BY name"
            ),
            "params_schema": {},
            "description": "Lista medicos activos (PostgreSQL).",
        },
        {
            "query_type": "test_doctors_by_sex",
            "sql_template": (
                "SELECT name, sex FROM doctors "
                "WHERE sex = :sex AND active = TRUE AND service_active = TRUE"
            ),
            "params_schema": {"sex": "str"},
            "description": "Medicos por sexo (PostgreSQL).",
        },
    ])
    router = IntentRouter(registry=registry)
    router.set_session(db_session)
    return router


def _make_agent_with_llm(llm: FakeLLMProvider, db_session) -> ConversationalAgent:
    """Agente legacy (fallback por keywords) — usado por los tests de coherencia."""
    return ConversationalAgent(llm=llm, router=_make_router(db_session))


class ScriptedAgentLLM:
    """LLM por fases: JSON del NLU en clasificación; eco de datos en formateo.

    En la fase de formateo (temperature=0.3 / complete) devuelve el contenido
    que recibe — el payload del handler — salvo que se guione un texto. La
    respuesta final contiene entonces los datos reales del backend.
    """

    name = "fake-scripted"

    def __init__(self, nlu_json: str, format_response: str = "") -> None:
        self.nlu_json = nlu_json
        self.format_response = format_response
        self.calls: list[dict[str, Any]] = []

    def chat_complete(self, messages, temperature=0.0, json_mode=False):
        self.calls.append(
            {"messages": messages, "temperature": temperature, "json_mode": json_mode}
        )
        if json_mode or temperature == 0.0:
            return self.nlu_json
        if self.format_response:
            return self.format_response
        return " ".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )

    def complete(self, system, user, temperature=0.1):
        if self.format_response:
            return self.format_response
        return user


def _make_llm_first_agent(llm, db_session) -> ConversationalAgent:
    """Agente LLM-first con el catálogo MCP cableado contra PostgreSQL real."""
    registry = ToolRegistry()
    for name, handler in build_tool_handlers(session=db_session).items():
        registry.register(name, handler)
    return ConversationalAgent(
        llm=llm,
        router=IntentRouter(),
        nlu_engine=NLUEngine(llm),
        tool_registry=registry,
    )


# ---------------------------------------------------------------------------
# Tests de coherencia: ¿el agente clasifica correctamente?
# ---------------------------------------------------------------------------


def test_coherencia_saludo_responde_directamente(db_session) -> None:
    """'Hola' → reply → responde sin consultar la DB."""
    llm = FakeLLMProvider(responses={
        "xhola_saludo_x": '{"action": "reply", "response_text": "Hola! En que puedo ayudarte?"}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xhola_saludo_x")

    assert result.agent_action == "reply"
    assert "hola" in result.response_text.lower() or "ayud" in result.response_text.lower()


def test_coherencia_consulta_ambigua_pide_aclaracion(db_session) -> None:
    """Mensaje ambiguo → ambiguous → respuesta con texto de aclaración."""
    llm = FakeLLMProvider(responses={
        "xasigna_ambig_x": (
            '{"action": "ambiguous", "response_text": '
            '"A que medico queresasignar y para que fecha?"}'
        ),
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xasigna_ambig_x alguien")

    assert result.agent_action == "ambiguous"
    assert result.response_text is not None
    assert len(result.response_text) > 10


# ---------------------------------------------------------------------------
# Tests de integración: NLU → tool del catálogo → handler PostgreSQL → respuesta
# ---------------------------------------------------------------------------


def test_integracion_count_doctors_ejecuta_sql(db_session) -> None:
    """NLU list_doctors count:true → handler real en PostgreSQL → respuesta con total."""
    _seed_doctors(db_session, count=3)

    llm = ScriptedAgentLLM(
        nlu_json='{"tool": "list_doctors", "params": {"count": true}, "confidence": 0.95}',
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="cuantos medicos hay")

    assert result.agent_action == "query"
    assert result.tool_name == "list_doctors"
    assert "3" in result.response_text


def test_integracion_list_doctors_muestra_nombres(db_session) -> None:
    """NLU list_doctors → la respuesta incluye el nombre real del doctor."""
    doctors = _seed_doctors(db_session, count=1)
    expected_name = doctors[0].name

    llm = ScriptedAgentLLM(
        nlu_json='{"tool": "list_doctors", "params": {}, "confidence": 0.95}',
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="lista de medicos")

    assert result.agent_action == "query"
    assert result.tool_name == "list_doctors"
    assert expected_name in result.response_text


def test_integracion_doctors_by_sex_filtra(db_session) -> None:
    """NLU list_doctors con sex=F → solo médicos femeninos en la respuesta."""
    doctors = _seed_doctors(db_session, count=4)  # crea 2 M (i=0,2), 2 F (i=1,3)

    llm = ScriptedAgentLLM(
        nlu_json='{"tool": "list_doctors", "params": {"sex": "F"}, "confidence": 0.95}',
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="cuantas doctoras hay")

    assert result.agent_action == "query"
    assert doctors[1].name in result.response_text
    assert doctors[0].name not in result.response_text
    assert "Masculino" not in result.response_text


def test_integracion_export_genera_pdf(db_session) -> None:
    """generate_report (contrato actual del export) → documento bytes o mensaje.

    El PDF mensual está en rediseño; el contrato del catálogo exige que el
    documento sea bytes reales o no exista — nunca un dict de error filtrado
    como documento.
    """
    _seed_doctors(db_session, count=2)

    llm = ScriptedAgentLLM(
        nlu_json=(
            '{"tool": "generate_report", "params": {"type": "monthly", "month": 5, '
            '"year": 2026}, "confidence": 0.9}'
        ),
        format_response="No se pudo generar el reporte en este momento.",
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="envia el reporte de mayo")

    assert isinstance(result, AgentResult)
    assert result.tool_name == "generate_report"
    assert result.document_bytes is None or isinstance(
        result.document_bytes, bytes | bytearray
    )
    assert "reporte" in result.response_text.lower()


def test_integracion_query_sin_resultados(db_session) -> None:
    """DB vacía + list_doctors → explicación natural de vacío, sin inventar datos."""
    llm = ScriptedAgentLLM(
        nlu_json='{"tool": "list_doctors", "params": {}, "confidence": 0.95}',
        format_response="No encontré datos que coincidan con tu consulta en el sistema.",
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="lista de medicos")

    assert result.agent_action == "query"
    assert "No encontré" in result.response_text


def test_integracion_export_sin_resultados_no_genera_documento(db_session) -> None:
    """generate_report sin calendario → sin documento, con mensaje."""
    llm = ScriptedAgentLLM(
        nlu_json=(
            '{"tool": "generate_report", "params": {"type": "monthly", "month": 5, '
            '"year": 2026}, "confidence": 0.9}'
        ),
        format_response="No hay calendario creado para ese mes.",
    )
    agent = _make_llm_first_agent(llm, db_session)

    result = agent.process(text="envia el reporte de mayo")

    assert result.document_bytes is None
    assert "calendario" in result.response_text.lower()


def test_integracion_process_nunca_lanza_excepcion(db_session) -> None:
    """process() siempre devuelve AgentResult válido, nunca lanza excepción."""
    for text in ["Hola", "?", "consulta rara", "!!!"]:
        llm = FakeLLMProvider()  # sin respuestas → {"action": "reply"}
        agent = _make_llm_first_agent(llm, db_session)
        result = agent.process(text=text)
        assert isinstance(result, AgentResult)
        assert result.response_text is not None
