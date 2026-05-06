"""
IntentRouter — routes classified intents to execution.

Receives {action, query_type, params, format} from the agent's LLM call
and handles execution: direct reply, database query, report export, or clarification.
"""

import logging
from typing import Any

from sqlalchemy import text as sa_text

from backend.app.application.telegram.types import AgentResult
from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES, QueryRegistry

logger = logging.getLogger(__name__)

_DEFAULT_NOT_FOUND = "No pude encontrar información sobre eso en el sistema."
_DEFAULT_AMBIGUOUS = (
    "Necesito un poco más de detalle para ayudarte. "
    "¿Podrías ser más específico?"
)
_DEFAULT_EXPORT_OK = "Aquí tienes el reporte solicitado."


class IntentRouter:
    """Routes classified intents to query execution, export, or direct reply."""

    def __init__(self, registry: QueryRegistry | None = None) -> None:
        self._registry = registry or QueryRegistry()
        self._registry.register_many(DEFAULT_QUERY_TYPES)
        self._session: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def registry(self) -> QueryRegistry:
        return self._registry

    def set_session(self, session: Any) -> None:
        """Set the DB session for query execution."""
        self._session = session

    def handle(
        self,
        *,
        action: str,
        query_type: str | None,
        params: dict[str, Any] | None,
        user_message: str = "",
        response_text: str | None = None,
        format: str | None = None,  # noqa: A002
    ) -> AgentResult:
        """Route an intent to the appropriate handler.

        Args:
            action: 'reply', 'query', 'export', or 'ambiguous'.
            query_type: Name of the registered query type (for query/export).
            params: Parameters to fill the SQL template.
            user_message: The original user message.
            response_text: Pre-built response (for reply/ambiguous actions).
            format: Output format for export ('pdf', 'excel', 'json').

        Returns:
            AgentResult with response text and optional document.
        """
        handler = {
            "reply": self._handle_reply,
            "query": self._handle_query,
            "export": self._handle_export,
            "ambiguous": self._handle_ambiguous,
        }.get(action)

        if handler is None:
            logger.warning("Unknown action '%s' in IntentRouter", action)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        return handler(
            query_type=query_type,
            params=params or {},
            user_message=user_message,
            response_text=response_text,
            format=format,
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_reply(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Direct reply — no data needed."""
        text = kwargs.get("response_text") or _DEFAULT_NOT_FOUND
        return AgentResult(response_text=text)

    def _handle_ambiguous(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Ask for clarification."""
        return AgentResult(response_text=_DEFAULT_AMBIGUOUS)

    def _handle_query(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a query and return a natural-language response."""
        query_type = kwargs.get("query_type")
        params = kwargs.get("params") or {}
        user_message = kwargs.get("user_message", "")

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para esa consulta.",
                    agent_action="query",
                )
            return AgentResult(
                response_text=self._format_rows(rows, columns, user_message),
                agent_action="query",
            )
        except Exception as exc:
            logger.warning("Query '%s' failed: %s", query_type, exc)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

    def _handle_export(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a query and return results as a PDF/Excel document."""
        query_type = kwargs.get("query_type")
        params = kwargs.get("params") or {}
        user_message = kwargs.get("user_message", "")
        fmt = kwargs.get("format", "pdf")

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para generar el reporte.",
                    agent_action="export",
                )

            return self._build_document(rows, columns, fmt, query_type)
        except Exception as exc:
            logger.warning("Export '%s' failed: %s", query_type, exc)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_template(self, sql_template: str, params: dict[str, Any]) -> tuple[list[dict], list[str]]:
        """Execute a parametrized SQL template and return (rows, columns)."""
        if self._session is None:
            logger.warning("No DB session set in IntentRouter")
            return [], []

        try:
            result = self._session.execute(sa_text(sql_template), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows, columns
        except Exception as exc:
            logger.warning("SQL execution failed: %s | SQL: %s", exc, sql_template[:120])
            return [], []

    def _format_rows(self, rows: list[dict], columns: list[str], user_message: str) -> str:
        """Generate a natural-language response from query results."""
        count = len(rows)
        if count == 0:
            return "No se encontraron resultados."
        if count == 1:
            first = rows[0]
            parts = [f"{k}: {v}" for k, v in first.items() if v is not None]
            return "Resultado: " + " | ".join(parts)
        if count <= 5:
            lines = [f"{i+1}. " + " | ".join(
                str(r.get(c, "")) for c in columns[:3]
            ) for i, r in enumerate(rows)]
            return f"Se encontraron {count} resultados:\n" + "\n".join(lines)
        return f"Se encontraron {count} resultados. Los primeros:\n" + "\n".join(
            f"{i+1}. " + " | ".join(str(r.get(c, "")) for c in columns[:3])
            for i, r in enumerate(rows[:5])
        )

    def _build_document(
        self,
        rows: list[dict],
        columns: list[str],
        fmt: str,
        query_type: str,
    ) -> AgentResult:
        """Build a PDF/Excel document from query results."""
        # For now, return text until DataExporter is built (Phase 2)
        return AgentResult(
            response_text=f"{_DEFAULT_EXPORT_OK} ({len(rows)} registros, formato {fmt.upper()}).",
            agent_action="export",
        )
