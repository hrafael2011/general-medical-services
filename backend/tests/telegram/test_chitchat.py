"""Tests for ChitchatHandler — deterministic, no SQL, no LLM."""

import pytest
from backend.app.application.telegram.chitchat import (
    ChitchatHandler,
)


class TestChitchatPatterns:
    @pytest.mark.parametrize(
        "text,expected_category",
        [
            ("Hola", "greeting"),
            ("Buenos dias", "greeting"),
            ("buenas tardes", "greeting"),
            ("hola, como estas", "greeting"),
            ("Gracias", "thanks"),
            ("muchas gracias por todo", "thanks"),
            ("te agradezco", "thanks"),
            ("Adios", "farewell"),
            ("chau", "farewell"),
            ("hasta luego", "farewell"),
            ("nos vemos", "farewell"),
            ("que puedes hacer", "help"),
            ("ayuda", "help"),
            ("que sabes hacer", "help"),
        ],
    )
    def test_matches_chitchat(self, text, expected_category):
        handler = ChitchatHandler()
        result = handler.match(text)
        assert result is not None
        assert result["category"] == expected_category

    @pytest.mark.parametrize(
        "text",
        [
            "cuantos medicos hay",
            "dame el calendario de mayo",
            "genera PDF de guardias",
            "quien esta de guardia manana",
            "DELETE FROM users",
            "cual es mi password",
        ],
    )
    def test_does_not_match_operational(self, text):
        handler = ChitchatHandler()
        result = handler.match(text)
        assert result is None, f"'{text}' should NOT match chitchat"


class TestChitchatResponses:
    def test_greeting_response_is_spanish(self):
        handler = ChitchatHandler()
        response = handler.respond("greeting")
        assert isinstance(response, str)
        assert len(response) > 0
        # Spanish greeting should contain common Spanish words
        assert any(
            word in response.lower()
            for word in ["hola", "buen", "puedo", "ayudarte", "asistente"]
        )

    def test_help_response_explains_capabilities(self):
        handler = ChitchatHandler()
        response = handler.respond("help")
        assert "medico" in response.lower() or "consultas" in response.lower()
        # Must NOT promise unrestricted access
        assert "base de datos" not in response.lower()

    def test_farewell_response_is_spanish(self):
        handler = ChitchatHandler()
        response = handler.respond("farewell")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_thanks_response_is_spanish(self):
        handler = ChitchatHandler()
        response = handler.respond("thanks")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_respond_unknown_returns_none(self):
        handler = ChitchatHandler()
        result = handler.respond("nonexistent_category")
        assert result is None

    def test_empty_text_returns_none(self):
        handler = ChitchatHandler()
        assert handler.match("") is None
        assert handler.match("   ") is None

    def test_handle_integration(self):
        handler = ChitchatHandler()
        result = handler.handle("Hola, buenos dias")
        assert result is not None
        assert result["category"] == "greeting"
        assert "asistente" in result["response_text"].lower()
        assert result["confidence"] == 0.99

    def test_handle_non_chitchat_returns_none(self):
        handler = ChitchatHandler()
        result = handler.handle("cuantos medicos hay")
        assert result is None
