from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.query_executor import (
    QueryExecutor,
    _EXCLUDE_TABLES,
    _build_schema_summary,
)


@pytest.fixture(scope="module")
def executor_no_db() -> QueryExecutor:
    """QueryExecutor with mocked session — for validation and extraction tests."""
    fake_session = MagicMock()
    fake_session.execute.side_effect = Exception("no DB")
    return QueryExecutor(session=fake_session, llm=FakeLLMProvider())


def test_users_table_is_excluded_from_schema(db_session: Session) -> None:
    """La tabla 'users' NO debe aparecer en el schema summary."""
    summary = _build_schema_summary(session=db_session)
    assert "TABLE users" not in summary


def test_exclude_tables_contains_users() -> None:
    """_EXCLUDE_TABLES incluye 'users'."""
    assert "users" in _EXCLUDE_TABLES


def test_exclude_tables_contains_sensitive_data() -> None:
    """_EXCLUDE_TABLES incluye tablas sensibles."""
    assert "telegram_interactions" in _EXCLUDE_TABLES
    assert "audit_logs" in _EXCLUDE_TABLES


def test_schema_summary_includes_doctors_table(db_session: Session) -> None:
    """La tabla 'doctors' debe aparecer en el summary."""
    summary = _build_schema_summary(session=db_session)
    assert "TABLE doctors" in summary


def test_schema_summary_returns_string(db_session: Session) -> None:
    """Schema summary es un string no vacío."""
    summary = _build_schema_summary(session=db_session)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_query_executor_validate_sql_blocks_dml(db_session: Session) -> None:
    """_validate_sql rechaza INSERT, UPDATE, DELETE, DROP."""
    llm = FakeLLMProvider()
    executor = QueryExecutor(session=db_session, llm=llm)

    assert executor._validate_sql("INSERT INTO doctors (name) VALUES ('x')") is False
    assert executor._validate_sql("UPDATE doctors SET name='x'") is False
    assert executor._validate_sql("DELETE FROM doctors") is False
    assert executor._validate_sql("DROP TABLE doctors") is False


def test_query_executor_validate_sql_allows_select(db_session: Session) -> None:
    """_validate_sql acepta SELECT statements."""
    llm = FakeLLMProvider()
    executor = QueryExecutor(session=db_session, llm=llm)

    assert executor._validate_sql("SELECT * FROM doctors") is True
    assert executor._validate_sql("SELECT COUNT(*) FROM doctors WHERE active = TRUE") is True


def test_query_executor_validate_sql_blocks_pg_sleep(db_session: Session) -> None:
    """_validate_sql rechaza PG_SLEEP."""
    llm = FakeLLMProvider()
    executor = QueryExecutor(session=db_session, llm=llm)

    assert executor._validate_sql("SELECT pg_sleep(10)") is False


def test_query_executor_extract_sql_from_markdown(executor_no_db: QueryExecutor) -> None:
    """_extract_sql extrae SQL de bloques ```sql ... ```."""
    text = "```sql\nSELECT * FROM doctors;\n```"
    result = executor_no_db._extract_sql(text)
    assert "SELECT * FROM doctors" in result


def test_query_executor_extract_sql_plain_text(executor_no_db: QueryExecutor) -> None:
    """_extract_sql devuelve texto plano como SQL."""
    text = "SELECT * FROM doctors"
    result = executor_no_db._extract_sql(text)
    assert result == "SELECT * FROM doctors"


def test_query_executor_run_sql_with_timeout_setting(db_session: Session) -> None:
    """_run_sql emite SET LOCAL statement_timeout antes de ejecutar."""
    llm = FakeLLMProvider()
    executor = QueryExecutor(session=db_session, llm=llm)

    result = executor._run_sql("SELECT 1 AS n")
    assert result["ok"] is True
    assert result["data"]["rows"][0]["n"] == 1


def test_execute_returns_generated_sql_for_auditing(db_session: Session) -> None:
    llm = FakeLLMProvider(responses={
        "cuantos": "SELECT COUNT(*) AS total FROM doctors",
    })
    executor = QueryExecutor(session=db_session, llm=llm)

    result = executor.execute("cuantos medicos tengo")

    assert result["ok"] is True
    assert result["sql"] == "SELECT COUNT(*) AS total FROM doctors"
    assert result["source"] == "nl_to_sql"


def test_query_executor_validate_sql_blocks_excluded_tables(db_session: Session) -> None:
    llm = FakeLLMProvider()
    executor = QueryExecutor(session=db_session, llm=llm)

    assert executor._validate_sql("SELECT * FROM users") is False
    assert executor._validate_sql("SELECT * FROM telegram_interactions") is False
    assert executor._validate_sql("SELECT * FROM audit_logs") is False


def test_execute_strips_internal_identifier_columns(db_session: Session) -> None:
    llm = FakeLLMProvider(responses={
        "ids": "SELECT id, name, rank_id FROM doctors LIMIT 100",
    })
    executor = QueryExecutor(session=db_session, llm=llm)

    result = executor.execute("dame ids de medicos")

    assert result["ok"] is True
    assert result["data"]["columns"] == ["name"]
    assert all("id" not in row for row in result["data"]["rows"])
    assert all("rank_id" not in row for row in result["data"]["rows"])
