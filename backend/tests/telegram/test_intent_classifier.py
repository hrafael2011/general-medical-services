"""Tests for IntentClassifier with FakeLLMProvider."""

import pytest

from backend.app.application.telegram.intent_classifier import (
    ClassifiedIntent,
    IntentClassifier,
)
from backend.app.application.telegram.llm import FakeLLMProvider


def _make_classifier(responses: dict[str, str] | None = None) -> IntentClassifier:
    """Create an IntentClassifier backed by FakeLLMProvider with scripted responses."""
    llm = FakeLLMProvider(responses=responses or {})
    return IntentClassifier(llm)


def _json_response(**kwargs) -> str:
    """Build a complete classification JSON string."""
    import json

    defaults = {
        "domain": "general",
        "action": "reply",
        "metric": None,
        "query_type": None,
        "params": {},
        "confidence": 1.0,
        "response_text": None,
        "format": None,
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


class TestIntentClassifier:
    def test_classifies_doctor_count_query(self):
        classifier = _make_classifier(
            {
                "cuantos medicos hay": _json_response(
                    domain="medicos",
                    action="query",
                    metric="total_doctors",
                    confidence=0.95,
                )
            }
        )
        result = classifier.classify("cuantos medicos hay")
        assert result.domain == "medicos"
        assert result.action == "query"
        assert result.metric == "total_doctors"
        assert result.confidence == 0.95

    def test_classifies_greeting_as_reply(self):
        classifier = _make_classifier(
            {
                "hola": _json_response(
                    domain="general",
                    action="reply",
                    response_text="¡Hola! ¿En que puedo ayudarte?",
                )
            }
        )
        result = classifier.classify("hola")
        assert result.domain == "general"
        assert result.action == "reply"
        assert result.response_text is not None

    def test_classifies_ambiguous_when_unclear(self):
        classifier = _make_classifier(
            {
                "asdfghjkl": _json_response(
                    domain="general",
                    action="ambiguous",
                    confidence=0.3,
                    response_text="No entiendo tu consulta",
                )
            }
        )
        result = classifier.classify("asdfghjkl")
        assert result.action == "ambiguous"
        assert result.confidence < 0.5

    def test_classifies_export_request(self):
        classifier = _make_classifier(
            {
                "reporte PDF": _json_response(
                    domain="medicos",
                    action="export",
                    metric="total_doctors",
                    confidence=0.9,
                    format="pdf",
                )
            }
        )
        result = classifier.classify("dame un reporte PDF de los medicos")
        assert result.action == "export"
        assert result.format == "pdf"

    def test_handles_malformed_json_gracefully(self):
        llm = FakeLLMProvider(responses={"cualquier cosa": "esto no es json"})
        classifier = IntentClassifier(llm)
        result = classifier.classify("cualquier cosa")
        assert result.action == "ambiguous"
        assert result.confidence == 0.0

    def test_handles_empty_response_gracefully(self):
        llm = FakeLLMProvider(responses={"cualquier cosa": ""})
        classifier = IntentClassifier(llm)
        result = classifier.classify("cualquier cosa")
        assert result.action == "ambiguous"
        assert result.confidence == 0.0

    def test_passes_entity_hints_to_llm(self):
        classifier = _make_classifier(
            {
                "cuantos hay": _json_response(
                    domain="medicos",
                    action="query",
                    metric="doctors_by_sex",
                    params={"sex": "male"},
                    confidence=0.9,
                )
            }
        )
        result = classifier.classify("cuantos hay", entity_hints="sex=male")
        assert result.metric == "doctors_by_sex"

    def test_parse_extracts_json_from_markdown_code_block(self):
        llm = FakeLLMProvider(
            responses={
                "test": '```json\n{"domain": "medicos", "action": "query", "metric": "total_doctors", "query_type": null, "params": {}, "confidence": 0.9, "response_text": null, "format": null}\n```'
            }
        )
        classifier = IntentClassifier(llm)
        result = classifier.classify("test")
        assert result.domain == "medicos"
        assert result.metric == "total_doctors"

    def test_defaults_on_missing_fields(self):
        llm = FakeLLMProvider(
            responses={"test": '{"action": "reply"}'}
        )
        classifier = IntentClassifier(llm)
        result = classifier.classify("test")
        assert result.domain == "general"  # default
        assert result.action == "reply"
        assert result.metric is None
        assert result.query_type is None
        assert result.params == {}
