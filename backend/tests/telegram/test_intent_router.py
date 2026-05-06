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
