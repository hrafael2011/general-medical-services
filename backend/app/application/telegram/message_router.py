"""TelegramMessageRouter — classifies user messages into route decisions.

Architecture:
  1. Deterministic pattern matching (fast, no LLM)
  2. LLM-based classification fallback (only when deterministic is ambiguous)
  3. Returns a TelegramRouteDecision that handlers consume
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.app.application.telegram.chitchat import ChitchatHandler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Route decision model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TelegramRouteDecision:
    """Immutable route decision produced by the router."""
    route: Literal[
        "chitchat",
        "operational_query",
        "report_request",
        "clarification",
        "unsupported",
    ]
    confidence: float
    reason: str
    normalized_text: str
    entities: dict[str, Any] = field(default_factory=dict)
    requested_format: Literal["text", "pdf", "excel"] | None = None
    requires_llm: bool = False


# ---------------------------------------------------------------------------
# Deterministic pattern groups
# ---------------------------------------------------------------------------

# Report request indicators — keywords that signal report/export intent
_REPORT_KEYWORDS = re.compile(
    r"\b(genera|generar|crea|crear|exporta|exportar|descarga|descargar|"
    r"m[aá]ndame|env[ií]a(me)?|dame|s[aá]ca(me)?|haz(me)?)\s"
    r"|"
    r"\b(PDF|Excel|reporte|listado|exportaci[oó]n|documento)\b",
    re.IGNORECASE,
)

_REPORT_FORMAT_PDF = re.compile(
    r"\b(PDF|pdf)\b"
)

_REPORT_FORMAT_EXCEL = re.compile(
    r"\b(Excel|excel|EXCEL|XLSX|xlsx|hoja\s+de\s+c[aá]lculo)\b",
    re.IGNORECASE,
)

# Destructive / prohibited keywords — immediate unsupported
_UNSUPPORTED_DESTRUCTIVE = re.compile(
    r"\b(elimina|eliminar|borra|borrar|DELETE|DROP|TRUNCATE|INSERT|UPDATE|ALTER|"
    r"cambia\s+(mi|la)\s+(contrase[ñn]a|password|clave)|"
    r"modifica\s+(mi|la)\s+(contrase[ñn]a|password|clave))\b",
    re.IGNORECASE,
)

# Secrets / auth probing — immediate unsupported
_UNSUPPORTED_SECRETS = re.compile(
    r"\b(password|contrase[ñn]a|token|JWT|secret|secreto|"
    r"hash|login\s+attempt|intento\s+de\s+login|"
    r"credencial|api[_\s]?key)\b",
    re.IGNORECASE,
)


class TelegramMessageRouter:
    """Routes Telegram messages to the appropriate handler path.

    Deterministic checks run first (chitchat patterns, report keywords,
    destructive/secret detection). Only routes that cannot be resolved
    deterministically go through LLM classification.
    """

    def __init__(self, llm_provider: Any | None = None) -> None:
        self._llm = llm_provider
        self._chitchat = ChitchatHandler()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> TelegramRouteDecision:
        """Classify *text* into a route decision.

        Deterministic checks run first. LLM classification only runs
        when deterministic checks are ambiguous.
        """
        if not text or not text.strip():
            return TelegramRouteDecision(
                route="clarification",
                confidence=1.0,
                reason="empty_message",
                normalized_text="",
            )

        normalized = text.strip()

        # 1. Chitchat check — greetings, thanks, farewell, help
        chitchat_result = self._chitchat.match(normalized)
        if chitchat_result is not None:
            return TelegramRouteDecision(
                route="chitchat",
                confidence=chitchat_result["confidence"],
                reason=f"chitchat_{chitchat_result['category']}_pattern",
                normalized_text=normalized.lower(),
                requires_llm=False,
            )

        # 2. Unsupported — destructive operations
        if _UNSUPPORTED_DESTRUCTIVE.search(normalized):
            return TelegramRouteDecision(
                route="unsupported",
                confidence=0.99,
                reason="destructive_pattern_detected",
                normalized_text=normalized.lower(),
                requires_llm=False,
            )

        # 3. Unsupported — secrets/auth probing
        if _UNSUPPORTED_SECRETS.search(normalized):
            return TelegramRouteDecision(
                route="unsupported",
                confidence=0.99,
                reason="secret_probe_pattern_detected",
                normalized_text=normalized.lower(),
                requires_llm=False,
            )

        # 4. Report requests — keywords indicating export/generation
        if _REPORT_KEYWORDS.search(normalized):
            requested_format = None
            if _REPORT_FORMAT_PDF.search(normalized):
                requested_format = "pdf"
            elif _REPORT_FORMAT_EXCEL.search(normalized):
                requested_format = "excel"

            return TelegramRouteDecision(
                route="report_request",
                confidence=0.90,
                reason="report_keyword_detected",
                normalized_text=normalized.lower(),
                requested_format=requested_format,
                requires_llm=True,  # Report parameter extraction uses LLM
            )

        # 5. Default — route to operational_query (existing agent handles it)
        return TelegramRouteDecision(
            route="operational_query",
            confidence=0.70,
            reason="default_operational_route",
            normalized_text=normalized.lower(),
            requires_llm=True,
        )
