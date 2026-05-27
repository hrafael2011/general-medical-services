"""
QueryExecutor — converts natural language questions to SQL and executes them.

This module is now a thin backward-compatible wrapper around the SQL Agent
orchestrator, which provides iterative self-correction (up to 3 turns) for
much higher accuracy on complex ad-hoc queries.

Security: only SELECT statements are allowed. DML/DDL are blocked.
"""

from __future__ import annotations

import time
from typing import Any

from backend.app.application.telegram.sql_agent import SQLAgentOrchestrator
from backend.app.application.telegram.sql_agent.security import (
    _EXCLUDE_TABLES,
    build_schema_summary,
    extract_sql_from_markdown,
    validate_sql,
)

# Re-export for backward compatibility in existing tests
_build_schema_summary = build_schema_summary


class QueryExecutor:
    """Backward-compatible wrapper that delegates to SQLAgentOrchestrator."""

    def __init__(self, session: Any, llm: Any) -> None:
        self._session = session
        self._llm = llm
        # Keep schema summary accessible for diagnostics / prompts
        self._schema_summary = build_schema_summary(session)
        # Internal orchestrator with multi-turn self-correction
        self._agent = SQLAgentOrchestrator(session, llm)

    def get_schema_summary(self) -> str:
        return self._schema_summary

    # ------------------------------------------------------------------
    # Backward-compat helpers (used by existing tests)
    # ------------------------------------------------------------------
    def _validate_sql(self, sql: str) -> bool:
        return validate_sql(sql)

    def _extract_sql(self, text: str) -> str:
        return extract_sql_from_markdown(text)

    def _run_sql(self, sql: str) -> dict:
        from backend.app.application.telegram.sql_agent.executor import SafeSQLExecutor
        return SafeSQLExecutor(self._session).run(sql)

    def _generate_sql(self, user_text: str) -> str:
        """Legacy single-turn generation (used by integration tests)."""
        from backend.app.application.telegram.sql_agent.generator import QueryGenerator
        from backend.app.application.telegram.sql_agent.schema_linker import SchemaLinker
        reduced = SchemaLinker(self._schema_summary).reduce(user_text)
        sql, _ = QueryGenerator(self._llm).generate(user_text, reduced)
        return sql

    def execute(
        self,
        nl_query: str,
        user_text: str = "",
        entity_hints: str = "",
    ) -> dict:
        """Execute a natural-language query via the SQL Agent.

        Returns:
            {"ok": True, "data": {...}, "sql": "...", "row_count": N, ...}
            or {"ok": False, "error": "..."}
        """
        start = time.perf_counter()
        result = self._agent.execute(
            nl_query=nl_query,
            user_text=user_text,
            entity_hints=entity_hints,
        )
        # Inject latency for observability
        if result.get("ok"):
            result.setdefault("data", {})
            result["data"]["elapsed_seconds"] = round(
                time.perf_counter() - start, 2
            )
        # Backward-compat: keep legacy source tag
        if result.get("source") == "nl_to_sql_agent":
            result["source"] = "nl_to_sql"
        return result
