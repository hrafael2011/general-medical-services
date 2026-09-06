"""Tests del NLUEngine — el clasificador vivo del bot (2026-09-05).

El antiguo IntentClassifier (domain/action/metric) ya no es el path público:
el agente clasifica con `NLUEngine`, que devuelve el nombre de UNA tool del
catálogo MCP de 22 tools (spec 15) con sus parámetros, o `reply` con
response_type (clarify/out_of_scope/greeting/help/farewell).

Contrato cubierto aquí (complementa test_mcp_catalog.py, que valida el
catálogo en sí):
- La respuesta JSON del LLM se parsea a nombre de tool real + params.
- needs_clarification activa la aclaración.
- Petición incoherente → reply/clarify; petición de escritura → reply/out_of_scope.
- JSON inválido / vacío / no-JSON → fallback conservador (clarify, confianza 0).
"""

import json

from backend.app.application.telegram.intent_classifier import NLUEngine, NLUResult
from backend.app.application.telegram.llm import FakeLLMProvider


def _make_engine(responses: dict[str, str] | None = None) -> NLUEngine:
    """NLUEngine respaldado por FakeLLMProvider con respuestas guionadas."""
    return NLUEngine(FakeLLMProvider(responses=responses or {}))


def _nlu_json(**kwargs) -> str:
    """Construye el JSON del contrato NLU (formato actual)."""
    defaults = {
        "tool": "reply",
        "params": {},
        "confidence": 0.95,
        "needs_clarification": False,
        "clarification_question": "",
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


class TestNLUEngine:
    def test_classifies_doctor_count_query_to_catalog_tool(self):
        """Pregunta canónica de conteo → tool real del catálogo con count."""
        engine = _make_engine(
            {
                "cuantos medicos hay": _nlu_json(
                    tool="list_doctors",
                    params={"count": True},
                    confidence=0.95,
                )
            }
        )
        result = engine.classify("cuantos medicos hay")
        assert isinstance(result, NLUResult)
        assert result.tool == "list_doctors"
        assert result.params.get("count") is True
        assert result.confidence == 0.95

    def test_classifies_greeting_as_reply_greeting(self):
        """Saludo → reply con response_type greeting."""
        engine = _make_engine(
            {
                "hola": _nlu_json(
                    tool="reply",
                    params={"response_type": "greeting"},
                    confidence=0.95,
                )
            }
        )
        result = engine.classify("hola")
        assert result.tool == "reply"
        assert result.params == {"response_type": "greeting"}
        assert not result.needs_clarification

    def test_classifies_ambiguous_when_unclear(self):
        """Petición incoherente → reply clarify (regla estricta del prompt)."""
        engine = _make_engine(
            {
                "asdfghjkl": _nlu_json(
                    tool="reply",
                    params={"response_type": "clarify"},
                    confidence=0.3,
                )
            }
        )
        result = engine.classify("asdfghjkl")
        assert result.tool == "reply"
        assert result.params == {"response_type": "clarify"}
        assert result.confidence < 0.5

    def test_missing_entity_requests_clarification(self):
        """needs_clarification → pregunta corta de aclaración."""
        engine = _make_engine(
            {
                "quien esta de guardia": _nlu_json(
                    tool="calendar_assignments",
                    params={},
                    confidence=0.7,
                    needs_clarification=True,
                    clarification_question="¿Para qué fecha quieres ver las guardias?",
                )
            }
        )
        result = engine.classify("quien esta de guardia")
        assert result.needs_clarification is True
        assert result.clarification_question == (
            "¿Para qué fecha quieres ver las guardias?"
        )

    def test_classifies_write_request_as_reply_out_of_scope(self):
        """Petición de escritura → reply out_of_scope (se hace en el panel web)."""
        engine = _make_engine(
            {
                "asigna a perez en emergencia": _nlu_json(
                    tool="reply",
                    params={"response_type": "out_of_scope"},
                    confidence=0.9,
                )
            }
        )
        result = engine.classify("asigna a perez en emergencia")
        assert result.tool == "reply"
        assert result.params == {"response_type": "out_of_scope"}

    def test_classifies_report_request_to_generate_report(self):
        """Pedido de reporte → tool generate_report (ya no hay action export)."""
        engine = _make_engine(
            {
                "reporte pdf": _nlu_json(
                    tool="generate_report",
                    params={"type": "monthly", "month": 5, "year": 2026},
                    confidence=0.9,
                )
            }
        )
        result = engine.classify("dame un reporte PDF de los medicos")
        assert result.tool == "generate_report"
        assert result.params["type"] == "monthly"

    def test_handles_malformed_json_gracefully(self):
        """JSON inválido → fallback conservador (clarify, confianza 0)."""
        llm = FakeLLMProvider(responses={"cualquier cosa": "esto no es json"})
        engine = NLUEngine(llm)
        result = engine.classify("cualquier cosa")
        assert result.tool == "reply"
        assert result.confidence == 0.0
        assert result.needs_clarification is True
        assert result.clarification_question

    def test_handles_empty_response_gracefully(self):
        """Respuesta vacía del LLM → fallback conservador."""
        llm = FakeLLMProvider(responses={"cualquier cosa": ""})
        engine = NLUEngine(llm)
        result = engine.classify("cualquier cosa")
        assert result.tool == "reply"
        assert result.confidence == 0.0
        assert result.needs_clarification is True

    def test_extracts_entities_into_params(self):
        """Los parámetros extraídos por el LLM viajan en params (sexo F)."""
        engine = _make_engine(
            {
                "cuantas doctoras hay": _nlu_json(
                    tool="list_doctors",
                    params={"sex": "F", "count": True},
                    confidence=0.9,
                )
            }
        )
        result = engine.classify("cuantas doctoras hay")
        assert result.tool == "list_doctors"
        assert result.params.get("sex") == "F"

    def test_parse_extracts_json_from_markdown_code_block(self):
        """JSON del LLM dentro de un fence markdown se parsea igual."""
        llm = FakeLLMProvider(
            responses={
                "test": (
                    '```json\n{"tool": "list_doctors", "params": {"count": true}, '
                    '"confidence": 0.9, "needs_clarification": false, '
                    '"clarification_question": ""}\n```'
                )
            }
        )
        engine = NLUEngine(llm)
        result = engine.classify("test")
        assert result.tool == "list_doctors"
        assert result.params == {"count": True}

    def test_defaults_on_missing_fields(self):
        """Campos ausentes → tool reply, params {}, confianza por defecto."""
        llm = FakeLLMProvider(responses={"test": '{"tool": "reply"}'})
        engine = NLUEngine(llm)
        result = engine.classify("test")
        assert result.tool == "reply"
        assert result.params == {}
        assert result.confidence == 0.5
        assert not result.needs_clarification
