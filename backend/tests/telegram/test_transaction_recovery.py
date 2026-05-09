"""Tests for PostgreSQL transaction recovery after SQL errors."""
import pytest
from backend.app.application.telegram.intent_router import IntentRouter


def test_router_recovers_after_sql_error(db_session):
    """After a failed SQL query, subsequent queries still work."""
    router = IntentRouter()
    router.set_session(db_session)

    # First query: invalid SQL -> should fail gracefully
    router.registry.register("bad_query", "SELECT * FROM nonexistent_table", {}, "broken")
    rows1, cols1 = router._execute_template(
        "SELECT * FROM nonexistent_table", {}
    )
    assert rows1 == []  # failed query returns empty

    # Second query: valid SQL -> MUST still work (rollback happened)
    router.registry.register("ok_query", "SELECT 1 AS val", {}, "ok")
    rows2, cols2 = router._execute_template("SELECT 1 AS val", {})
    assert len(rows2) == 1
    assert rows2[0]["val"] == 1


def test_query_executor_recovers_after_sql_error(db_session):
    """After QueryExecutor executes invalid SQL, subsequent valid SQL works."""
    from backend.app.application.telegram.llm import FakeLLMProvider
    from backend.app.application.telegram.query_executor import QueryExecutor

    sql_llm = FakeLLMProvider(responses={
        "invalid": "SELECT * FROM nonexistent_table",
    })
    qe = QueryExecutor(db_session, sql_llm)

    # First: execute invalid SQL -> should fail but recover
    result1 = qe.execute("invalid")
    assert result1["ok"] is False

    # Second: execute valid query -> MUST work
    result2 = qe._run_sql("SELECT 1 AS val")
    assert result2["ok"] is True
    assert result2["data"]["rows"][0]["val"] == 1
