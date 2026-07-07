"""QueryGenerator — generates SQL using Chain-of-Thought prompting."""

from __future__ import annotations

from typing import Any

from backend.app.application.telegram.sql_agent.security import extract_sql_from_markdown


_COT_SYSTEM_PROMPT = (
    "Eres un experto en PostgreSQL. Generas consultas SELECT seguras y eficientes.\n"
    "{system_context}"
    "PIENSA paso a paso antes de escribir SQL:\n"
    "1. ¿Qué tablas necesito?\n"
    "2. ¿Qué JOINs requiero?\n"
    "3. ¿Qué filtros WHERE aplico?\n"
    "4. ¿Qué agregaciones GROUP BY / ORDER BY necesito?\n"
    "5. ¿Necesito LIMIT?\n"
    "Después de razonar, escribe SOLO el SQL final entre triple backticks (```sql)."
)


class QueryGenerator:
    """Generates SQL from natural language using a Chain-of-Thought prompt."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def generate(
        self,
        user_text: str,
        reduced_schema: str,
        entity_hints: str = "",
        few_shot_examples: str = "",
        system_context: str = "",
    ) -> tuple[str, str]:
        """Return (sql, reasoning) where reasoning is the LLM's thought process.

        If the LLM does not produce reasoning separately, reasoning is empty.
        """
        entity_section = ""
        if entity_hints:
            entity_section = (
                f"\n\nENTIDADES DETECTADAS (usa estos valores exactos):\n{entity_hints}\n"
            )

        example_section = ""
        if few_shot_examples:
            example_section = (
                f"\n\nEJEMPLOS DE CONSULTAS SIMILARES:\n{few_shot_examples}\n"
            )

        system_context_section = ""
        if system_context:
            system_context_section = f"\n\nCONTEXTO DEL SISTEMA:\n{system_context}\n"

        system_content = _COT_SYSTEM_PROMPT.format(system_context=system_context_section)

        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": (
                    f"Esquema de la base de datos (tablas relevantes):\n\n"
                    f"{reduced_schema}"
                    f"{entity_section}"
                    f"{example_section}"
                    f"\n\nPregunta del usuario: {user_text}\n\n"
                    f"Razona paso a paso y luego escribe el SQL final."
                ),
            },
        ]
        response = self._llm.chat_complete(messages, temperature=0.1)
        sql = extract_sql_from_markdown(response)
        # Heuristic: everything before the first ``` is reasoning
        reasoning = ""
        code_block = response.find("```")
        if code_block > 0:
            reasoning = response[:code_block].strip()
        return sql, reasoning
