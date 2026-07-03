"""ChitchatHandler — deterministic Spanish conversational responses.

Rules:
  - No database queries.
  - No SQL Agent calls.
  - No LLM calls.
  - No report generation.
  - No operational data leakage.
  - Spanish responses only.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Pattern definitions — each pattern maps to a category
# Order matters: more specific patterns first
# ---------------------------------------------------------------------------

CHITCHAT_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Greetings
    ("greeting", re.compile(
        r"\b(hola|buen(os|as)\s*(d[ií]as?|tardes?|noches?)|hey|qu[eé]\s*tal|saludos)\b",
        re.IGNORECASE,
    )),
    # Thanks
    ("thanks", re.compile(
        r"\b(gracias|te\s+agradezco|muchas?\s*gracias|mil\s*gracias|agradecid[oa])\b",
        re.IGNORECASE,
    )),
    # Farewell
    ("farewell", re.compile(
        r"\b(adi[oó]s|chau|chao|hasta\s*luego|nos\s*vemos|bye|me\s*despido)\b",
        re.IGNORECASE,
    )),
    # Help / capability explanation
    ("help", re.compile(
        r"\b(qu[eé]\s*(puedes{1,2}|sabes)\s*(hacer|ayudarme)|ayuda|help|"
        r"como\s*(funcionas|te\s*uso|puedes{1,2}\s*ayudarme)|"
        r"qu[eé]\s*herramientas|capacidades|qu[eé]\s*consultas)\b",
        re.IGNORECASE,
    )),
]

# ---------------------------------------------------------------------------
# Fixed Spanish responses per category
# ---------------------------------------------------------------------------

_FIXED_RESPONSES: dict[str, str] = {
    "greeting": (
        "¡Hola! Soy el asistente de turnos médicos. "
        "Puedo ayudarte con consultas sobre médicos, disponibilidad, "
        "calendarios, guardias, misiones y reportes disponibles en el sistema."
    ),
    "thanks": "¡De nada! Estoy aquí para ayudarte con tus consultas operativas.",
    "farewell": "¡Hasta luego! Quedo disponible cuando necesites consultar información del sistema.",
    "help": (
        "Puedo ayudarte con consultas sobre médicos, disponibilidad, calendarios, "
        "guardias, misiones y reportes disponibles en el sistema.\n\n"
        "Por ejemplo:\n"
        "• \"¿Cuántos médicos activos hay?\"\n"
        "• \"¿Quiénes están de guardia mañana?\"\n"
        "• \"Dame el calendario de julio en PDF\"\n"
        "• \"¿Cuáles son las misiones activas?\""
    ),
}


class ChitchatHandler:
    """Deterministic handler for conversational messages.

    Matches greetings, thanks, farewell, and help requests using
    regex patterns. Returns None for anything that looks operational.
    """

    def match(self, text: str) -> dict[str, Any] | None:
        """Try to match *text* against known chitchat patterns.

        Returns:
            {"category": str, "confidence": float} if matched, None otherwise.
        """
        if not text or not text.strip():
            return None

        normalized = text.strip().lower()

        for category, pattern in CHITCHAT_PATTERNS:
            if pattern.search(normalized):
                return {"category": category, "confidence": 0.99}

        return None

    def respond(self, category: str) -> str | None:
        """Return the fixed Spanish response for *category*, or None."""
        return _FIXED_RESPONSES.get(category)

    def handle(self, text: str) -> dict[str, Any] | None:
        """Match and respond in one call. Returns None if not chitchat.

        Returns:
            {"response_text": str, "category": str, "confidence": float} or None
        """
        match_result = self.match(text)
        if match_result is None:
            return None

        response = self.respond(match_result["category"])
        if response is None:
            return None

        return {
            "response_text": response,
            "category": match_result["category"],
            "confidence": match_result["confidence"],
        }
