"""Tests for Pydantic schemas in telegram.schemas."""

import pytest
from backend.app.application.telegram.schemas import IntentOutput


def test_intent_output_valid_query_action() -> None:
    """IntentOutput acepta un JSON de accion query completo."""
    data = {
        "action": "query",
        "query_type": "count_doctors_total",
        "params": {},
        "confidence": 0.95,
        "missing_fields": [],
        "requires_clarification": False,
    }
    result = IntentOutput.model_validate(data)
    assert result.action == "query"
    assert result.query_type == "count_doctors_total"
    assert result.confidence == 0.95


def test_intent_output_valid_export_action() -> None:
    """IntentOutput acepta action=export con format=excel."""
    data = {
        "action": "export",
        "query_type": "list_active_doctors",
        "params": {"format": "excel"},
        "format": "excel",
        "confidence": 0.88,
    }
    result = IntentOutput.model_validate(data)
    assert result.action == "export"
    assert result.format == "excel"


def test_intent_output_reply_action() -> None:
    """IntentOutput acepta action=reply con response_text."""
    data = {
        "action": "reply",
        "response_text": "Hola! En que puedo ayudarte?",
        "confidence": 1.0,
    }
    result = IntentOutput.model_validate(data)
    assert result.action == "reply"
    assert result.response_text == "Hola! En que puedo ayudarte?"


def test_intent_output_ambiguous_with_clarification() -> None:
    """IntentOutput acepta action=ambiguous con requires_clarification=True."""
    data = {
        "action": "ambiguous",
        "response_text": "En que area queres buscar?",
        "missing_fields": ["area"],
        "requires_clarification": True,
        "confidence": 0.6,
    }
    result = IntentOutput.model_validate(data)
    assert result.action == "ambiguous"
    assert result.requires_clarification is True
    assert "area" in result.missing_fields


def test_intent_output_unknown_action_rejected() -> None:
    """Action fuera de las permitidas lanza ValidationError."""
    with pytest.raises(Exception):
        IntentOutput.model_validate({"action": "delete_all", "confidence": 0.5})


def test_intent_output_defaults() -> None:
    """Campos con default se rellenan correctamente."""
    data = {"action": "reply"}
    result = IntentOutput.model_validate(data)
    assert result.params == {}
    assert result.missing_fields == []
    assert result.confidence == 1.0
    assert result.requires_clarification is False
    assert result.query_type is None
    assert result.response_text is None
    assert result.format is None


def test_intent_output_confidence_range() -> None:
    """confidence fuera de [0,1] lanza ValidationError."""
    data = {"action": "reply", "confidence": 1.5}
    with pytest.raises(Exception):
        IntentOutput.model_validate(data)


def test_intent_output_format_only_valid_values() -> None:
    """format debe ser 'pdf', 'excel', o None."""
    data = {"action": "export", "format": "word"}
    with pytest.raises(Exception):
        IntentOutput.model_validate(data)
