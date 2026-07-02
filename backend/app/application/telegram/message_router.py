"""TelegramMessageRouter — classifies user messages into route decisions.

Architecture:
  1. Deterministic pattern matching (fast, no LLM)
  2. LLM-based classification fallback (only when deterministic is ambiguous)
  3. Returns a TelegramRouteDecision that handlers consume
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)


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
