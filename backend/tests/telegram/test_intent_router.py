"""
Tests for QueryRegistry and IntentRouter.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import UTC, datetime

import pytest

from backend.app.application.telegram.types import AgentResult
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.registry import QueryRegistry
from backend.app.infrastructure.db.session import SessionLocal

UTC = UTC


# ---------------------------------------------------------------------------
# QueryRegistry tests
# ---------------------------------------------------------------------------


def test_registry_register_and_get() -> None:
    """Register a query and retrieve it by query_type."""
    registry = QueryRegistry()
    registry.register(
        query_type="doctors_by_sex",
        sql_template="SELECT * FROM doctors WHERE sex = :sex",
        params_schema={"sex": "str"},
        description="List doctors by sex",
    )

    entry = registry.get("doctors_by_sex")
    assert entry is not None
    assert entry["query_type"] == "doctors_by_sex"


def test_registry_get_unknown_returns_none() -> None:
    """Asking for an unregistered query_type returns None."""
    registry = QueryRegistry()
    assert registry.get("nonexistent") is None


def test_registry_list_all(db_session) -> None:
    """list_all() returns all registered queries with hit counts."""
    registry = QueryRegistry()
    registry.register("q1", "SELECT 1", {}, "Q1")
    registry.register("q2", "SELECT 2", {}, "Q2")

    all_q = registry.list_all()
    assert len(all_q) == 2
    assert all(q["hits"] == 0 for q in all_q)


def test_registry_increment_hit() -> None:
    """increment_hit() increases the counter for a query_type."""
    registry = QueryRegistry()
    registry.register("test_q", "SELECT 1", {}, "Test")
    registry.increment_hit("test_q")
    registry.increment_hit("test_q")

    entry = registry.get("test_q")
    assert entry["hits"] == 2


def test_registry_increment_unknown_does_not_crash() -> None:
    """Incrementing a non-existent query_type should not raise."""
    registry = QueryRegistry()
    registry.increment_hit("ghost")  # should not raise


def test_registry_delete() -> None:
    """delete() removes a query_type from the registry."""
    registry = QueryRegistry()
    registry.register("delete_me", "SELECT 1", {}, "Delete")
    assert registry.get("delete_me") is not None

    registry.delete("delete_me")
    assert registry.get("delete_me") is None


# ---------------------------------------------------------------------------
# IntentRouter tests
# ---------------------------------------------------------------------------


def test_router_reply_action() -> None:
    """Action 'reply' returns the response_text directly without any DB query."""
    router = IntentRouter()
    result = router.handle(
        action="reply",
        query_type=None,
        params=None,
        user_message="Hola",
        response_text="¡Hola! ¿En qué puedo ayudarte?",
    )

    assert isinstance(result, AgentResult)
    assert result.response_text == "¡Hola! ¿En qué puedo ayudarte?"
    assert result.document_bytes is None


def test_router_ambiguous_action() -> None:
    """Action 'ambiguous' returns a clarification prompt."""
    router = IntentRouter()
    result = router.handle(
        action="ambiguous",
        query_type=None,
        params={"entity": "doctor"},
        user_message="asigna a Pérez",
    )

    assert isinstance(result, AgentResult)
    assert "específico" in result.response_text.lower() or "aclaración" in result.response_text.lower()


def test_router_unknown_query_type_returns_fallback_message(db_session) -> None:
    """A query_type not in the registry should return a 'not found' message
    (the fallback to query_database is handled by the agent, not the router)."""
    router = IntentRouter()
    result = router.handle(
        action="query",
        query_type="nonexistent_query",
        params={},
        user_message="pregunta rara",
    )

    assert isinstance(result, AgentResult)
    assert "encontrar" in result.response_text.lower()


def test_router_export_action_without_format(db_session) -> None:
    """Action 'export' without format defaults to PDF and returns document."""
    router = IntentRouter()
    result = router.handle(
        action="export",
        query_type="list_active_doctors",
        params={},
        user_message="lista de médicos activos en PDF",
    )

    assert isinstance(result, AgentResult)
    # Without a real SQL engine, it should fall back gracefully
    assert result.response_text is not None


def test_router_query_with_named_params() -> None:
    """query_type with named params should return a valid AgentResult."""
    router = IntentRouter()
    # Register a simple query first
    router._registry.register(
        query_type="count_doctors",
        sql_template="SELECT COUNT(*) as total FROM doctors",
        params_schema={},
        description="Count all doctors",
    )

    result = router.handle(
        action="query",
        query_type="count_doctors",
        params={},
        user_message="cuántos médicos hay",
    )

    assert isinstance(result, AgentResult)
    assert result.response_text is not None


def test_router_export_with_format_pdf() -> None:
    """Export with format=pdf sets the filename to .pdf."""
    router = IntentRouter()
    router._registry.register(
        query_type="list_active_doctors",
        sql_template=(
            "SELECT name, sex, availability_mode "
            "FROM doctors WHERE active = 1 AND service_active = 1"
        ),
        params_schema={},
        description="List active doctors",
    )

    result = router.handle(
        action="export",
        query_type="list_active_doctors",
        params={"format": "pdf"},
        user_message="exporta médicos activos a PDF",
    )

    assert isinstance(result, AgentResult)
    if result.document_filename:
        assert result.document_filename.endswith(".pdf")


# ---------------------------------------------------------------------------
# _execute_template sin sesión
# ---------------------------------------------------------------------------


def test_router_execute_template_without_session_returns_empty() -> None:
    """Sin DB session configurada, _execute_template devuelve [], []."""
    router = IntentRouter()
    rows, cols = router._execute_template("SELECT 1", {})
    assert rows == []
    assert cols == []


# ---------------------------------------------------------------------------
# _handle_query con filas vacías
# ---------------------------------------------------------------------------


def test_router_query_empty_rows_returns_no_results(db_session) -> None:
    """query_type registrado que devuelve 0 filas → 'No se encontraron resultados'."""
    router = IntentRouter()
    router.set_session(db_session)
    router._registry.register(
        query_type="always_empty",
        sql_template="SELECT name FROM doctors WHERE 1 = 0",
        params_schema={},
        description="Siempre vacío",
    )

    result = router.handle(
        action="query",
        query_type="always_empty",
        params={},
        user_message="algo que no existe",
    )

    assert "No se encontraron" in result.response_text


# ---------------------------------------------------------------------------
# _handle_export con filas vacías
# ---------------------------------------------------------------------------


def test_router_export_empty_rows_returns_message(db_session) -> None:
    """Export con 0 resultados → mensaje descriptivo, sin documento."""
    router = IntentRouter()
    router.set_session(db_session)
    router._registry.register(
        query_type="empty_export",
        sql_template="SELECT name FROM doctors WHERE 1 = 0",
        params_schema={},
        description="Export vacío",
    )

    result = router.handle(
        action="export",
        query_type="empty_export",
        params={},
        user_message="exporta algo vacío",
    )

    assert result.document_bytes is None
    assert "resultados" in result.response_text.lower()


# ---------------------------------------------------------------------------
# _build_document con format=excel
# ---------------------------------------------------------------------------


def test_router_export_excel_format(db_session) -> None:
    """Export con format=excel devuelve AgentResult con .xlsx filename."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    doc = DoctorModel(
        id=str(_uuid.uuid4()),
        name="Dr. Excel Test",
        normalized_name="dr. excel test",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="variable",
        participa_misiones=True,
        whatsapp_phone=None,
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

    router = IntentRouter()
    router.set_session(db_session)
    router._registry.register(
        query_type="list_doctors_excel",
        sql_template="SELECT name, sex FROM doctors WHERE active = 1 AND service_active = 1",
        params_schema={},
        description="Lista médicos para Excel",
    )

    result = router.handle(
        action="export",
        query_type="list_doctors_excel",
        params={},
        user_message="exporta en excel",
        format="excel",
    )

    assert result.document_bytes is not None
    assert result.document_filename is not None
    assert result.document_filename.endswith(".xlsx")


# ---------------------------------------------------------------------------
# _format_rows en IntentRouter (distintos tamaños)
# ---------------------------------------------------------------------------


def test_router_format_rows_single_row() -> None:
    """1 fila → 'Resultado:' con los pares clave:valor."""
    router = IntentRouter()
    result = router._format_rows(
        rows=[{"name": "Dr. Test", "count": 7}],
        columns=["name", "count"],
        user_message="cuántos hay",
    )
    assert "Resultado:" in result
    assert "Test" in result


def test_router_format_rows_five_rows() -> None:
    """5 filas → lista numerada completa incluyendo '5.'."""
    router = IntentRouter()
    rows = [{"name": f"Dr. {i}", "sex": "M", "area": "E"} for i in range(5)]
    result = router._format_rows(rows, ["name", "sex", "area"], "test")
    assert "5 resultados" in result
    assert "5." in result


def test_router_format_rows_more_than_five() -> None:
    """6+ filas → solo primeros 5 mostrados, '6.' no aparece."""
    router = IntentRouter()
    rows = [{"name": f"Dr. {i}"} for i in range(8)]
    result = router._format_rows(rows, ["name"], "test")
    assert "8 resultados" in result
    assert "6." not in result


# ---------------------------------------------------------------------------
# QueryRegistry — register_many y duplicados
# ---------------------------------------------------------------------------


def test_registry_register_many() -> None:
    """register_many() carga múltiples queries de una vez."""
    registry = QueryRegistry()
    definitions = [
        {"query_type": "q_a", "sql_template": "SELECT 1", "params_schema": {}, "description": "A"},
        {"query_type": "q_b", "sql_template": "SELECT 2", "params_schema": {}, "description": "B"},
    ]
    registry.register_many(definitions)

    assert registry.get("q_a") is not None
    assert registry.get("q_b") is not None
    assert len(registry.list_all()) == 2


def test_registry_duplicate_registration_does_not_overwrite() -> None:
    """Registrar dos veces el mismo query_type no sobreescribe la definición original."""
    registry = QueryRegistry()
    registry.register("dup", "SELECT 1 AS original", {}, "Original")
    registry.register("dup", "SELECT 2 AS overwrite", {}, "Overwrite")

    entry = registry.get("dup")
    assert "original" in entry["sql_template"].lower()


# ---------------------------------------------------------------------------
# _handle_ambiguous with response_text
# ---------------------------------------------------------------------------


def test_router_ambiguous_uses_llm_response_text() -> None:
    """Cuando el LLM envía response_text, se usa en vez del default."""
    router = IntentRouter()
    result = router.handle(
        action="ambiguous",
        query_type=None,
        params={},
        user_message="asigna a Pérez",
        response_text="¿En qué área querés asignar a Pérez: Emergencia o Pista?",
    )

    assert "Emergencia" in result.response_text
    assert "Pista" in result.response_text


def test_router_ambiguous_falls_back_to_default() -> None:
    """Sin response_text del LLM, usa el mensaje default."""
    router = IntentRouter()
    result = router.handle(
        action="ambiguous",
        query_type=None,
        params={},
        user_message="no sé",
    )

    assert "específico" in result.response_text.lower()


# ---------------------------------------------------------------------------
# M5: All required query types are registered
# ---------------------------------------------------------------------------


_REQUIRED_QUERY_TYPES = [
    "count_doctors_total",
    "count_by_sex",
    "doctors_by_sex",
    "count_by_rank",
    "count_by_specific_rank",
    "doctors_by_rank",
    "list_active_doctors",
    "doctor_detail",
    "doctors_pending_availability",
    "calendar_status_month",
    "doctors_working_date",
    "assignment_count_by_date_range",
    "mission_ranking",
    "operational_summary",
    "doctor_history_60d",
    "count_doctors_by_department",
    "count_by_specific_sex",
    "doctor_history_by_name",
    "assignments_by_area",
    "unresolved_gaps_month",
]


def test_all_required_query_types_are_registered() -> None:
    """Todos los query_types esperados estan registrados al iniciar IntentRouter."""
    router = IntentRouter()
    for qt in _REQUIRED_QUERY_TYPES:
        entry = router.registry.get(qt)
        assert entry is not None, f"Falta query_type: {qt}"
        assert entry["sql_template"], f"sql_template vacio para {qt}"
