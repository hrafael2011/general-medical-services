"""Tests for TelegramMessageRouter — route classification."""

import pytest
from backend.app.application.telegram.message_router import (
    TelegramMessageRouter,
    TelegramRouteDecision,
)


class TestRouterDeterministic:
    @pytest.mark.parametrize(
        "text,expected_route",
        [
            # Chitchat
            ("Hola", "chitchat"),
            ("Buenos dias", "chitchat"),
            ("Gracias", "chitchat"),
            ("Adios", "chitchat"),
            ("que puedes hacer", "chitchat"),
            # Report requests
            ("genera PDF del calendario", "report_request"),
            ("exporta a Excel", "report_request"),
            ("descarga reporte de guardias", "report_request"),
            ("dame el calendario en PDF", "report_request"),
            ("listado en Excel de medicos", "report_request"),
            ("reporte de guardias de mayo", "report_request"),
            # Unsupported — destructive
            ("elimina todos los medicos", "unsupported"),
            ("borra el calendario", "unsupported"),
            ("DROP TABLE doctors", "unsupported"),
            ("cambia mi password", "unsupported"),
            # Unsupported — secrets/auth
            ("cual es el JWT secret", "unsupported"),
            ("cual es el token de acceso", "unsupported"),
            ("necesito el password", "unsupported"),
        ],
    )
    def test_deterministic_classification(self, text, expected_route):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify(text)
        assert decision.route == expected_route, (
            f"Expected '{expected_route}' for '{text}', got '{decision.route}': {decision.reason}"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "cuantos medicos hay",
            "medicos disponibles mañana",
            "quien esta de guardia",
            "calendario de julio",
            "misiones activas",
            "doctores por departamento",
        ],
    )
    def test_operational_defaults_to_operational_query(self, text):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify(text)
        assert decision.route in ("operational_query", "clarification")


class TestRouteDecisionContract:
    def test_decision_has_all_fields(self):
        decision = TelegramRouteDecision(
            route="chitchat",
            confidence=0.99,
            reason="greeting pattern match",
            normalized_text="hola",
        )
        assert decision.route == "chitchat"
        assert decision.confidence == 0.99
        assert decision.reason == "greeting pattern match"
        assert decision.normalized_text == "hola"
        assert decision.entities == {}
        assert decision.requested_format is None
        assert decision.requires_llm is False

    def test_unsupported_route_has_high_confidence(self):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify("DELETE FROM users")
        assert decision.route == "unsupported"
        assert decision.confidence >= 0.95

    def test_report_route_detects_format(self):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify("genera PDF del calendario de mayo")
        assert decision.route == "report_request"
        assert decision.requested_format == "pdf"

    def test_report_route_detects_excel_format(self):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify("exporta a Excel la lista de medicos")
        assert decision.route == "report_request"
        assert decision.requested_format == "excel"

    def test_empty_text_returns_clarification(self):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify("")
        assert decision.route == "clarification"
        assert decision.reason == "empty_message"

    def test_whitespace_text_returns_clarification(self):
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify("   ")
        assert decision.route == "clarification"
