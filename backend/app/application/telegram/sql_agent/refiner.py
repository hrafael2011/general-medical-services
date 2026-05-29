"""QueryRefiner — regenerates SQL after an error or critique."""

from __future__ import annotations

from typing import Any

from backend.app.application.telegram.sql_agent.security import extract_sql_from_markdown


_REFINER_SYSTEM_PROMPT = (
    "Eres un experto en PostgreSQL. Corrige una consulta SQL basándote en el error "
    "o la crítica recibida. Razona brevemente el cambio y luego escribe SOLO el SQL "
    "corregido entre triple backticks (```sql)."
)


class QueryRefiner:
    """Re-generates SQL given an error message or critique."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def refine(
        self,
        user_text: str,
        previous_sql: str,
        critique: str,
        reduced_schema: str,
        entity_hints: str = "",
    ) -> tuple[str, str]:
        """Return (new_sql, reasoning).

        *critique* can be a database error message or a critique from the verifier.
        """
        entity_section = ""
        if entity_hints:
            entity_section = (
                f"\n\nENTIDADES DETECTADAS (usa estos valores exactos):\n{entity_hints}\n"
            )

        messages = [
            {"role": "system", "content": _REFINER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Esquema de la base de datos:\n\n{reduced_schema}"
                    f"{entity_section}\n\n"
                    f"Pregunta del usuario: {user_text}\n\n"
                    f"SQL anterior: {previous_sql}\n\n"
                    f"Error / Crítica: {critique}\n\n"
                    f"Corrige el SQL y escribe el nuevo código."
                ),
            },
        ]
        response = self._llm.chat_complete(messages, temperature=0.1)
        sql = extract_sql_from_markdown(response)
        reasoning = ""
        code_block = response.find("```")
        if code_block > 0:
            reasoning = response[:code_block].strip()
        return sql, reasoning
