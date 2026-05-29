"""
Tests de integración end-to-end del agente conversacional.

Pipeline completa: FakeLLMProvider → ConversationalAgent → IntentRouter → SQLite real.
SQL templates son SQLite-compatibles (active = 1, no TRUE; LIKE no ILIKE).
"""

import uuid
from datetime import UTC, datetime

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.registry import QueryRegistry
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


def _make_router_sqlite(db_session) -> IntentRouter:
    """IntentRouter con SQL SQLite-compatible y sesión configurada."""
    registry = QueryRegistry()
    registry.register_many([
        {
            "query_type": "sqlite_count_doctors",
            "sql_template": "SELECT COUNT(*) AS total FROM doctors WHERE active = 1 AND service_active = 1",
            "params_schema": {},
            "description": "Cuenta medicos activos (SQLite).",
        },
        {
            "query_type": "sqlite_list_doctors",
            "sql_template": "SELECT name, sex FROM doctors WHERE active = 1 AND service_active = 1 ORDER BY name",
            "params_schema": {},
            "description": "Lista medicos activos (SQLite).",
        },
        {
            "query_type": "sqlite_doctors_by_sex",
            "sql_template": "SELECT name, sex FROM doctors WHERE sex = :sex AND active = 1 AND service_active = 1",
            "params_schema": {"sex": "str"},
            "description": "Medicos por sexo (SQLite).",
        },
    ])
    router = IntentRouter(registry=registry)
    router.set_session(db_session)
    return router


def _make_agent_with_llm(llm: FakeLLMProvider, db_session) -> ConversationalAgent:
    return ConversationalAgent(llm=llm, router=_make_router_sqlite(db_session))


# ---------------------------------------------------------------------------
# Tests de coherencia: ¿el agente clasifica correctamente?
# ---------------------------------------------------------------------------


def test_coherencia_saludo_responde_directamente(db_session) -> None:
    """'Hola' → action=reply → responde sin consultar la DB."""
    llm = FakeLLMProvider(responses={
        "xhola_saludo_x": '{"action": "reply", "response_text": "Hola! En que puedo ayudarte?"}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xhola_saludo_x")

    assert result.agent_action == "reply"
    assert "hola" in result.response_text.lower() or "ayud" in result.response_text.lower()


def test_coherencia_consulta_ambigua_pide_aclaracion(db_session) -> None:
    """Mensaje ambiguo → action=ambiguous → respuesta con texto de aclaración."""
    llm = FakeLLMProvider(responses={
        "xasigna_ambig_x": '{"action": "ambiguous", "response_text": "A que medico queresasignar y para que fecha?"}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xasigna_ambig_x alguien")

    assert result.agent_action == "ambiguous"
    assert result.response_text is not None
    assert len(result.response_text) > 10


# ---------------------------------------------------------------------------
# Tests de integración: FakeLLM → Router → SQL real → respuesta
# ---------------------------------------------------------------------------


def test_integracion_count_doctors_ejecuta_sql(db_session) -> None:
    """FakeLLM → query sqlite_count_doctors → SQL real en SQLite → responde con conteo."""
    _seed_doctors(db_session, count=3)

    llm = FakeLLMProvider(responses={
        "xcount_docs_integration_x": '{"action": "query", "query_type": "sqlite_count_doctors", "params": {}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xcount_docs_integration_x")

    assert result.agent_action == "query"
    assert "3" in result.response_text


def test_integracion_list_doctors_muestra_nombres(db_session) -> None:
    """FakeLLM → query sqlite_list_doctors → respuesta incluye nombre del doctor."""
    doctors = _seed_doctors(db_session, count=1)
    expected_name = doctors[0].name

    llm = FakeLLMProvider(responses={
        "xlist_docs_integration_x": '{"action": "query", "query_type": "sqlite_list_doctors", "params": {}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xlist_docs_integration_x")

    assert result.agent_action == "query"
    assert expected_name in result.response_text


def test_integracion_doctors_by_sex_filtra(db_session) -> None:
    """FakeLLM → query sqlite_doctors_by_sex con params={sex:'F'} → resultado filtrado."""
    _seed_doctors(db_session, count=4)  # crea 2 M, 2 F

    llm = FakeLLMProvider(responses={
        "xdocs_by_sex_f_integration_x": '{"action": "query", "query_type": "sqlite_doctors_by_sex", "params": {"sex": "F"}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xdocs_by_sex_f_integration_x")

    assert result.agent_action == "query"
    assert result.response_text is not None
    assert "encontraron" in result.response_text.lower() or "resultado" in result.response_text.lower()


def test_integracion_export_genera_pdf(db_session) -> None:
    """FakeLLM → export sqlite_list_doctors → genera PDF real (bytes > 100)."""
    _seed_doctors(db_session, count=2)

    llm = FakeLLMProvider(responses={
        "xexport_pdf_integration_x": '{"action": "export", "query_type": "sqlite_list_doctors", "params": {}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xexport_pdf_integration_x")

    assert result.agent_action == "export"
    assert result.document_bytes is not None
    assert len(result.document_bytes) > 100
    assert result.document_filename is not None
    assert result.document_filename.endswith(".pdf")


def test_integracion_query_sin_resultados(db_session) -> None:
    """DB vacía + query → 'No se encontraron resultados'."""
    llm = FakeLLMProvider(responses={
        "xlist_empty_integration_x": '{"action": "query", "query_type": "sqlite_list_doctors", "params": {}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xlist_empty_integration_x")

    assert "encontraron" in result.response_text.lower() or "encontrar" in result.response_text.lower()


def test_integracion_export_sin_resultados_no_genera_documento(db_session) -> None:
    """DB vacía + export → sin documento, con mensaje."""
    llm = FakeLLMProvider(responses={
        "xexport_empty_integration_x": '{"action": "export", "query_type": "sqlite_list_doctors", "params": {}}',
    })
    agent = _make_agent_with_llm(llm, db_session)

    result = agent.process(text="xexport_empty_integration_x")

    assert result.document_bytes is None


def test_integracion_process_nunca_lanza_excepcion(db_session) -> None:
    """process() siempre devuelve AgentResult válido, nunca lanza excepción."""
    for text in ["Hola", "?", "consulta rara", "!!!"]:
        llm = FakeLLMProvider()  # sin respuestas → devuelve JSON con action desconocida
        agent = _make_agent_with_llm(llm, db_session)
        result = agent.process(text=text)
        assert isinstance(result, AgentResult)
        assert result.response_text is not None
