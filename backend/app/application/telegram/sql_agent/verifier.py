"""SQLVerifier — evaluates whether the generated SQL answers the user's question."""

from __future__ import annotations

from typing import Any


_VERIFIER_SYSTEM_PROMPT = (
    "Eres un auditor de calidad de consultas SQL. Evalúa si una consulta SQL "
    "responde correctamente la pregunta del usuario.\n"
    "Responde SOLO con un JSON válido: {\"verdict\": \"correct\" | \"incorrect\", \"reason\": \"...\"}"
)


class SQLVerifier:
    """Uses the LLM to self-critique a generated SQL query."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def verify(
        self,
        user_text: str,
        sql: str,
        execution_result: dict | None,
    ) -> dict:
        """Return {"verdict": "correct" | "incorrect", "reason": str}.

        If execution_result is None or empty rows, the verifier checks whether
        "no results" is a plausible correct answer.
        """
        row_count = 0
        sample_rows: list[dict] = []
        if execution_result and execution_result.get("ok"):
            data = execution_result.get("data", {})
            row_count = data.get("row_count", 0)
            sample_rows = data.get("rows", [])[:3]

        result_summary = f"Filas devueltas: {row_count}."
        if sample_rows:
            result_summary += f"\nMuestra: {sample_rows}"

        messages = [
            {"role": "system", "content": _VERIFIER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Pregunta del usuario: {user_text}\n\n"
                    f"SQL generado: {sql}\n\n"
                    f"Resultado de ejecución: {result_summary}\n\n"
                    f"¿El SQL responde correctamente la pregunta? "
                    f"Responde con el JSON."
                ),
            },
        ]
        response = self._llm.chat_complete(messages, temperature=0.0, json_mode=True)
        response = response.strip()
        return self._parse_verdict(response)

    @staticmethod
    def _parse_verdict(text: str) -> dict:
        import json
        import re

        # Try to extract JSON block
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
        try:
            parsed = json.loads(text)
            verdict = parsed.get("verdict", "incorrect")
            reason = parsed.get("reason", "Sin explicación.")
            return {"verdict": verdict, "reason": reason}
        except json.JSONDecodeError:
            # Fallback: keyword-based heuristic
            if "correct" in text.lower():
                return {"verdict": "correct", "reason": text}
            return {"verdict": "incorrect", "reason": text or "No se pudo evaluar."}
