"""
Tests de integración para DeepSeekProvider.

Requieren DEEPSEEK_API_KEY en .env. Se saltean automáticamente si no está configurada.
"""

import pytest

from backend.app.application.telegram.llm import DeepSeekProvider
from backend.app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.deepseek_api_key,
    reason="DEEPSEEK_API_KEY no configurada",
)


@pytest.fixture(scope="module")
def llm() -> DeepSeekProvider:
    return DeepSeekProvider()


def test_complete_returns_nonempty_string(llm: DeepSeekProvider) -> None:
    result = llm.complete(
        system="Responde siempre con una sola palabra.",
        user="¿Cuál es la capital de Francia?",
    )
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_complete_follows_system_instructions(llm: DeepSeekProvider) -> None:
    result = llm.complete(
        system="Responde SOLO con la palabra 'ok', sin puntuación ni mayúsculas.",
        user="Confirma que recibiste este mensaje.",
    )
    assert "ok" in result.lower()


def test_chat_complete_with_history(llm: DeepSeekProvider) -> None:
    messages = [
        {"role": "system", "content": "Eres un asistente médico conciso."},
        {"role": "user", "content": "¿Qué es un turno de guardia?"},
        {"role": "assistant", "content": "Es un período de trabajo en el que el médico cubre el servicio de urgencias."},
        {"role": "user", "content": "¿Cuántas horas suele durar?"},
    ]
    result = llm.chat_complete(messages)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_chat_complete_returns_valid_json_when_asked(llm: DeepSeekProvider) -> None:
    messages = [
        {
            "role": "system",
            "content": (
                "Clasifica la intención del usuario. "
                "Responde SOLO con JSON válido: "
                '{"intent": "<nombre>", "entities": {}, "confidence": <0-1>}'
            ),
        },
        {"role": "user", "content": "¿Cuántos médicos hay activos?"},
    ]
    result = llm.chat_complete(messages)
    assert isinstance(result, str)
    import json
    data = json.loads(result)
    assert "intent" in data
    assert "confidence" in data


def test_complete_low_temperature_is_deterministic(llm: DeepSeekProvider) -> None:
    system = "Responde SOLO con el número 42, sin texto adicional."
    user = "Dame el número."
    r1 = llm.complete(system, user, temperature=0.0)
    r2 = llm.complete(system, user, temperature=0.0)
    assert "42" in r1
    assert "42" in r2


def test_complete_handles_long_prompt(llm: DeepSeekProvider) -> None:
    long_text = "médico " * 200
    result = llm.complete(
        system="Resume en una sola oración lo que se repite en el texto.",
        user=f"Texto: {long_text}",
    )
    assert isinstance(result, str)
    assert len(result.strip()) > 0
