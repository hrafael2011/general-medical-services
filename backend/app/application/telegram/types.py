"""Shared types for the Telegram conversational agent pipeline."""

from dataclasses import dataclass


@dataclass
class AgentResult:
    response_text: str
    document_bytes: bytes | None = None
    document_filename: str | None = None
    agent_action: str = "direct"
    tool_name: str | None = None
    tool_entities: dict | None = None
    tool_result: dict | None = None


@dataclass
class RouteDecision:
    """Internal route decision passed through the orchestrator pipeline."""
    route: str  # "chitchat" | "operational_query" | "report_request" | "clarification" | "unsupported"
    confidence: float
    reason: str
    normalized_text: str
    entities: dict | None = None
    requested_format: str | None = None  # "text", "pdf", "excel"
    requires_llm: bool = False
