"""Pydantic schemas for validating LLM structured output."""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


_VALID_ACTIONS = {"query", "export", "reply", "ambiguous"}
_VALID_FORMATS = {"pdf", "excel"}


class IntentOutput(BaseModel):
    """Validated output from the LLM interpreter."""

    action: str = Field(description="query | export | reply | ambiguous")
    query_type: str | None = Field(default=None, description="Registered query type name")
    params: dict = Field(default_factory=dict, description="Parameters for the SQL template")
    response_text: str | None = Field(default=None, description="Pre-built text for reply/ambiguous")
    format: str | None = Field(default=None, description="Export format: pdf or excel")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    missing_fields: list[str] = Field(default_factory=list, description="Fields missing from the request")
    requires_clarification: bool = Field(default=False, description="Whether the user needs to clarify")

    @field_validator("action")
    @classmethod
    def action_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_ACTIONS:
            raise ValueError(f"action must be one of {_VALID_ACTIONS}, got '{v}'")
        return v

    @field_validator("format")
    @classmethod
    def format_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_FORMATS:
            raise ValueError(f"format must be one of {_VALID_FORMATS}, got '{v}'")
        return v


ResolveStatus = Literal["resolved", "ambiguous", "not_found"]


@dataclass
class ResolveResult:
    """Normalized result from EntityResolver entity-resolution methods.

    All resolve_* methods return this structure so callers don't need
    to infer status from list length or isinstance checks.
    """

    status: ResolveStatus
    matches: list[dict[str, Any]] = field(default_factory=list)
