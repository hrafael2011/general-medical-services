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
