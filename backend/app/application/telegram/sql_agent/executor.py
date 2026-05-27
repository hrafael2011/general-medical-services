"""SafeSQLExecutor — thin wrapper around execute_sql_safely."""

from __future__ import annotations

from typing import Any

from backend.app.application.telegram.sql_agent.security import execute_sql_safely, validate_sql


class SafeSQLExecutor:
    """Executes SQL safely after validation."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def run(self, sql: str) -> dict:
        """Validate and execute SQL. Return a standard result dict."""
        if not validate_sql(sql):
            return {
                "ok": False,
                "error": "Solo se permiten consultas SELECT.",
                "sql": sql,
            }
        result = execute_sql_safely(self._session, sql)
        result["sql"] = sql
        return result
