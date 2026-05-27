"""Tests for the SQL Agent multi-turn fallback pipeline."""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.orm import Session

from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.sql_agent import (
    SQLAgentOrchestrator,
    SQLVerifier,
    SchemaLinker,
    build_schema_summary,
    validate_sql,
)
from backend.app.application.telegram.sql_agent.executor import SafeSQLExecutor
from backend.app.application.telegram.sql_agent.generator import QueryGenerator
from backend.app.application.telegram.sql_agent.refiner import QueryRefiner
from backend.app.application.telegram.sql_agent.security import extract_sql_from_markdown
from backend.app.infrastructure.db.models.doctors import DoctorModel

_NOW = datetime.datetime.now(tz=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Security / utilities
# ---------------------------------------------------------------------------


class TestSecurityUtils:
    def test_validate_sql_blocks_insert(self) -> None:
        assert validate_sql("INSERT INTO doctors VALUES (1)") is False

    def test_validate_sql_blocks_update(self) -> None:
        assert validate_sql("UPDATE doctors SET name='x'") is False

    def test_validate_sql_blocks_delete(self) -> None:
        assert validate_sql("DELETE FROM doctors") is False

    def test_validate_sql_allows_select(self) -> None:
        assert validate_sql("SELECT * FROM doctors") is True

    def test_validate_sql_blocks_excluded_table(self) -> None:
        assert validate_sql("SELECT * FROM users") is False

    def test_extract_sql_from_markdown(self) -> None:
        text = "```sql\nSELECT 1\n```"
        assert extract_sql_from_markdown(text) == "SELECT 1"

    def test_extract_sql_plain(self) -> None:
        assert extract_sql_from_markdown("SELECT 1") == "SELECT 1"


# ---------------------------------------------------------------------------
# SchemaLinker
# ---------------------------------------------------------------------------


class TestSchemaLinker:
    def test_reduces_schema_for_doctor_query(self) -> None:
        full = build_schema_summary()
        linker = SchemaLinker(full)
        reduced = linker.reduce("cuantos medicos hay")
        assert "doctors" in reduced
        assert "calendars" not in reduced

    def test_reduces_schema_for_calendar_query(self) -> None:
        full = build_schema_summary()
        linker = SchemaLinker(full)
        reduced = linker.reduce("asignaciones del calendario")
        assert "calendar_assignments" in reduced
        # Related tables pulled in via FK heuristics
        assert "doctors" in reduced

    def test_falls_back_to_full_schema_on_unknown(self) -> None:
        full = build_schema_summary()
        linker = SchemaLinker(full)
        reduced = linker.reduce("xyz unknown topic")
        assert reduced == full


# ---------------------------------------------------------------------------
# SafeSQLExecutor
# ---------------------------------------------------------------------------


class TestSafeSQLExecutor:
    def test_blocks_forbidden_sql(self, db_session: Session) -> None:
        executor = SafeSQLExecutor(db_session)
        result = executor.run("DROP TABLE doctors")
        assert result["ok"] is False
        assert "Solo se permiten" in result["error"]

    def test_executes_valid_select(self, db_session: Session) -> None:
        db_session.add(DoctorModel(
            id="d-agent-1", name="Dr. Agent", normalized_name="dr. agent",
            sex="male", active=True, service_active=True, whatsapp_phone="0000000000",
            created_at=_NOW, updated_at=_NOW,
        ))
        db_session.commit()
        executor = SafeSQLExecutor(db_session)
        result = executor.run('SELECT * FROM doctors WHERE id = \'d-agent-1\'')
        assert result["ok"] is True
        assert result["data"]["row_count"] == 1


# ---------------------------------------------------------------------------
# QueryGenerator (with FakeLLM)
# ---------------------------------------------------------------------------


class TestQueryGenerator:
    def test_generates_sql(self) -> None:
        llm = FakeLLMProvider(responses={
            "cuantos medicos": "```sql\nSELECT COUNT(*) AS total FROM doctors\n```"
        })
        gen = QueryGenerator(llm)
        sql, reasoning = gen.generate(
            user_text="cuantos medicos hay",
            reduced_schema="TABLE doctors: ...",
        )
        assert "SELECT" in sql
        assert "COUNT(*)" in sql

    def test_returns_reasoning_before_code_block(self) -> None:
        llm = FakeLLMProvider(responses={
            "test": "Primero cuento.\n```sql\nSELECT 1\n```"
        })
        gen = QueryGenerator(llm)
        sql, reasoning = gen.generate(user_text="test", reduced_schema="")
        assert "Primero cuento" in reasoning
        assert "SELECT 1" in sql


# ---------------------------------------------------------------------------
# SQLVerifier (with FakeLLM)
# ---------------------------------------------------------------------------


class TestSQLVerifier:
    def test_verifies_correct_sql(self) -> None:
        llm = FakeLLMProvider(responses={
            "cuantos medicos": '{"verdict": "correct", "reason": "Responde bien."}'
        })
        verifier = SQLVerifier(llm)
        result = verifier.verify(
            user_text="cuantos medicos",
            sql="SELECT COUNT(*) FROM doctors",
            execution_result={"ok": True, "data": {"row_count": 5}},
        )
        assert result["verdict"] == "correct"

    def test_verifies_incorrect_sql(self) -> None:
        llm = FakeLLMProvider(responses={
            "cuantos medicos": '{"verdict": "incorrect", "reason": "Suma mal."}'
        })
        verifier = SQLVerifier(llm)
        result = verifier.verify(
            user_text="cuantos medicos",
            sql="SELECT SUM(id) FROM doctors",
            execution_result={"ok": True, "data": {"row_count": 1}},
        )
        assert result["verdict"] == "incorrect"


# ---------------------------------------------------------------------------
# QueryRefiner (with FakeLLM)
# ---------------------------------------------------------------------------


class TestQueryRefiner:
    def test_refines_after_error(self) -> None:
        llm = FakeLLMProvider(responses={
            "corrige": "```sql\nSELECT COUNT(*) FROM doctors\n```"
        })
        refiner = QueryRefiner(llm)
        sql, reasoning = refiner.refine(
            user_text="cuantos medicos",
            previous_sql="SELECT COUT(*) FROM doctors",
            critique='ERROR: column "COUT" does not exist',
            reduced_schema="TABLE doctors: ...",
        )
        assert "SELECT" in sql


# ---------------------------------------------------------------------------
# SQLAgentOrchestrator end-to-end (with FakeLLM)
# ---------------------------------------------------------------------------


class TestSQLAgentOrchestrator:
    def test_success_on_first_iteration(self, db_session: Session) -> None:
        db_session.add(DoctorModel(
            id="d-orch-1", name="Dr. Orch", normalized_name="dr. orch",
            sex="male", active=True, service_active=True, whatsapp_phone="0000000000",
            created_at=_NOW, updated_at=_NOW,
        ))
        db_session.commit()

        llm = FakeLLMProvider(responses={
            "Razona paso a paso": "```sql\nSELECT COUNT(*) AS total FROM doctors\n```",
            "Responde con el JSON": '{"verdict": "correct", "reason": "OK"}',
        })
        agent = SQLAgentOrchestrator(db_session, llm)
        result = agent.execute(nl_query="cuantos medicos hay")
        assert result["ok"] is True
        assert result["sql"] == "SELECT COUNT(*) AS total FROM doctors"
        assert result["data"]["row_count"] == 1
        assert result.get("iterations") == 1

    def test_recovers_after_syntax_error(self, db_session: Session) -> None:
        db_session.add(DoctorModel(
            id="d-orch-2", name="Dr. Orch2", normalized_name="dr. orch2",
            sex="female", active=True, service_active=True, whatsapp_phone="0000000000",
            created_at=_NOW, updated_at=_NOW,
        ))
        db_session.commit()

        llm = FakeLLMProvider(responses={
            "Razona paso a paso": "```sql\nSELECT COUT(*) FROM doctors\n```",
            "Corrige el SQL": "```sql\nSELECT COUNT(*) AS total FROM doctors\n```",
            "Responde con el JSON": '{"verdict": "correct", "reason": "OK"}',
        })
        agent = SQLAgentOrchestrator(db_session, llm)
        result = agent.execute(nl_query="cuantos medicos hay")
        assert result["ok"] is True
        assert result["sql"] == "SELECT COUNT(*) AS total FROM doctors"
        # Should take 2 iterations: generate (fail) → refine (success)
        assert result.get("iterations") == 2

    def test_gives_up_after_max_iterations(self, db_session: Session) -> None:
        llm = FakeLLMProvider(responses={
            "Razona paso a paso": "```sql\nSELECT bad\n```",
            "Corrige el SQL": "```sql\nSELECT also_bad\n```",
            "Responde con el JSON": '{"verdict": "incorrect", "reason": "Nope"}',
        })
        agent = SQLAgentOrchestrator(db_session, llm)
        result = agent.execute(nl_query="cuantos medicos hay")
        # After 3 failed iterations it returns an error (execution never succeeded)
        assert result["ok"] is False
        assert "Falló tras 3 intentos" in result["error"]
        assert result.get("sql") == "SELECT also_bad"


# ---------------------------------------------------------------------------
# Backward compatibility: QueryExecutor still works
# ---------------------------------------------------------------------------


class TestQueryExecutorBackwardCompat:
    def test_query_executor_delegates_to_agent(self, db_session: Session) -> None:
        from backend.app.application.telegram.query_executor import QueryExecutor

        db_session.add(DoctorModel(
            id="d-legacy-1", name="Dr. Legacy", normalized_name="dr. legacy",
            sex="male", active=True, service_active=True, whatsapp_phone="0000000000",
            created_at=_NOW, updated_at=_NOW,
        ))
        db_session.commit()

        llm = FakeLLMProvider(responses={
            "legacy": "```sql\nSELECT name FROM doctors WHERE id = 'd-legacy-1' LIMIT 1\n```",
            "verifica": '{"verdict": "correct", "reason": "OK"}',
        })
        executor = QueryExecutor(db_session, llm)
        result = executor.execute("legacy test query")
        assert result["ok"] is True
        assert result["sql"] == "SELECT name FROM doctors WHERE id = 'd-legacy-1' LIMIT 1"
        assert "data" in result


# ---------------------------------------------------------------------------
# ExampleStore
# ---------------------------------------------------------------------------


class TestExampleStore:
    def test_add_and_search(self) -> None:
        from backend.app.application.telegram.sql_agent.example_store import (
            ExampleStore,
            SQLExample,
        )

        store = ExampleStore(db_path=":memory:")
        store.clear()
        store.add([
            SQLExample("cuantos medicos hay", "SELECT COUNT(*) FROM doctors", "count"),
            SQLExample("lista de doctores", "SELECT name FROM doctors", "list"),
            SQLExample("servicios por mes", "SELECT month, COUNT(*) FROM calendars GROUP BY month", "analytics"),
        ])
        assert store.count() == 3
        results = store.search("cuantos doctores", k=2)
        assert len(results) == 2
        assert any("COUNT(*)" in r.sql for r in results)
        store.close()

    def test_empty_store_returns_nothing(self) -> None:
        from backend.app.application.telegram.sql_agent.example_store import ExampleStore

        store = ExampleStore(db_path=":memory:")
        store.clear()
        assert store.search("cualquier cosa", k=3) == []
        store.close()

    def test_clear_removes_all(self) -> None:
        from backend.app.application.telegram.sql_agent.example_store import (
            ExampleStore,
            SQLExample,
        )

        store = ExampleStore(db_path=":memory:")
        store.add([SQLExample("test", "SELECT 1", "test")])
        assert store.count() == 1
        store.clear()
        assert store.count() == 0
        store.close()


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_builds_few_shot_block(self) -> None:
        from backend.app.application.telegram.sql_agent.example_store import (
            ExampleStore,
            SQLExample,
        )
        from backend.app.application.telegram.sql_agent.prompt_builder import (
            PromptBuilder,
        )

        store = ExampleStore(db_path=":memory:")
        store.add([
            SQLExample("cuantos medicos", "SELECT COUNT(*) FROM doctors", "count"),
        ])
        builder = PromptBuilder(store)
        block = builder.build_few_shot("cuantos doctores hay", k=1)
        assert "SELECT COUNT(*) FROM doctors" in block
        assert "Ejemplo 1" in block
        store.close()

    def test_returns_empty_when_no_store(self) -> None:
        from backend.app.application.telegram.sql_agent.prompt_builder import (
            PromptBuilder,
        )

        builder = PromptBuilder(None)
        assert builder.build_few_shot("test") == ""

    def test_wrap_prompt_inserts_block(self) -> None:
        from backend.app.application.telegram.sql_agent.prompt_builder import (
            PromptBuilder,
        )

        builder = PromptBuilder(None)
        wrapped = builder.wrap_prompt("Pregunta final", "Ejemplo previo")
        assert "Ejemplo previo" in wrapped
        assert "Pregunta final" in wrapped

    def test_wrap_prompt_skips_when_empty(self) -> None:
        from backend.app.application.telegram.sql_agent.prompt_builder import (
            PromptBuilder,
        )

        builder = PromptBuilder(None)
        wrapped = builder.wrap_prompt("Pregunta final", "")
        assert wrapped == "Pregunta final"
