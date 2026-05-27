"""SQLAgentOrchestrator — multi-turn SQL generation with self-correction.

Coordinates SchemaLinker → QueryGenerator → SafeSQLExecutor → SQLVerifier →
QueryRefiner (up to MAX_ITERATIONS) to produce correct SQL.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.application.telegram.sql_agent.executor import SafeSQLExecutor
from backend.app.application.telegram.sql_agent.generator import QueryGenerator
from backend.app.application.telegram.sql_agent.refiner import QueryRefiner
from backend.app.application.telegram.sql_agent.schema_linker import SchemaLinker
from backend.app.application.telegram.sql_agent.security import build_schema_summary
from backend.app.application.telegram.sql_agent.verifier import SQLVerifier

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


class SQLAgentOrchestrator:
    """Drop-in replacement for QueryExecutor with iterative self-correction."""

    def __init__(self, session: Any, llm: Any) -> None:
        self._session = session
        self._llm = llm
        self._schema_linker = SchemaLinker(build_schema_summary(session))
        self._generator = QueryGenerator(llm)
        self._executor = SafeSQLExecutor(session)
        self._verifier = SQLVerifier(llm)
        self._refiner = QueryRefiner(llm)

    # ------------------------------------------------------------------
    # Public API (same signature as legacy QueryExecutor.execute)
    # ------------------------------------------------------------------
    def execute(
        self,
        nl_query: str,
        user_text: str = "",
        entity_hints: str = "",
    ) -> dict:
        """Execute a natural-language query via the multi-turn SQL Agent.

        Returns the same dict format as the legacy QueryExecutor so it can be
        swapped in without changing callers.
        """
        context = user_text or nl_query
        iteration = 0
        sql = ""
        reasoning = ""
        reduced_schema = self._schema_linker.reduce(context)

        # --- Iteration 0: initial generation ---
        sql, reasoning = self._generator.generate(
            user_text=context,
            reduced_schema=reduced_schema,
            entity_hints=entity_hints,
        )
        if not sql:
            return {"ok": False, "error": "No se pudo generar una consulta SQL."}

        while iteration < MAX_ITERATIONS:
            iteration += 1
            logger.info("SQL Agent iteration %d | SQL: %s...", iteration, sql[:80])

            # Execute
            exec_result = self._executor.run(sql)

            # If execution failed, refine immediately
            if not exec_result.get("ok"):
                error_msg = exec_result.get("error", "Error desconocido")
                if iteration >= MAX_ITERATIONS:
                    return {
                        "ok": False,
                        "error": f"Falló tras {MAX_ITERATIONS} intentos. Último error: {error_msg}",
                        "sql": sql,
                    }
                sql, reasoning = self._refiner.refine(
                    user_text=context,
                    previous_sql=sql,
                    critique=error_msg,
                    reduced_schema=reduced_schema,
                    entity_hints=entity_hints,
                )
                if not sql:
                    return {"ok": False, "error": "No se pudo regenerar SQL tras el error."}
                continue

            # Execution succeeded → verify semantics
            verification = self._verifier.verify(
                user_text=context,
                sql=sql,
                execution_result=exec_result,
            )

            if verification.get("verdict") == "correct":
                # Success
                exec_result["source"] = "nl_to_sql_agent"
                exec_result["iterations"] = iteration
                exec_result["reasoning"] = reasoning
                return exec_result

            # Verification failed → refine
            critique = verification.get("reason", "La consulta no responde la pregunta correctamente.")
            if iteration >= MAX_ITERATIONS:
                # Return last result anyway, but mark as uncertain
                exec_result["source"] = "nl_to_sql_agent"
                exec_result["iterations"] = iteration
                exec_result["warning"] = (
                    f"No se logró verificar la corrección tras {MAX_ITERATIONS} intentos. "
                    f"Última crítica: {critique}"
                )
                return exec_result

            sql, reasoning = self._refiner.refine(
                user_text=context,
                previous_sql=sql,
                critique=critique,
                reduced_schema=reduced_schema,
                entity_hints=entity_hints,
            )
            if not sql:
                return {"ok": False, "error": "No se pudo regenerar SQL tras la verificación."}

        # Should never reach here
        return {"ok": False, "error": "Agotados intentos de corrección."}
