"""Tests del guard de reply en la arquitectura LLM-first (2026-09-05).

Hoy el guard es arquitectónico: la tool `reply` del catálogo responde con
copy fijo del agente por response_type (greeting/help/farewell/clarify/
out_of_scope) — el texto del LLM nunca se filtra a la respuesta. Un LLM que
intente contestar un pedido de datos con reply no puede inventar resultados:
los datos solo provienen de los handlers del catálogo.
"""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_classifier import NLUEngine
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.types import AgentResult


class ReplyGuardRouterStub(IntentRouter):
    """Stub que devuelve ok para cualquier handle() call."""

    def handle(self, **kwargs):
        return AgentResult(response_text="ok")


def _make_llm_first_agent(llm) -> ConversationalAgent:
    """Agente LLM-first mínimo para el guard de reply."""
    return ConversationalAgent(
        llm=llm,
        router=ReplyGuardRouterStub(),
        nlu_engine=NLUEngine(llm),
    )


def test_valid_reply_uses_fixed_help_copy():
    """Reply help → copy fijo real del agente (el texto del LLM no se filtra)."""
    llm = FakeLLMProvider(responses={
        "ayuda": (
            '{"tool": "reply", "params": {"response_type": "help"}, '
            '"confidence": 0.9}'
        ),
    })
    agent = _make_llm_first_agent(llm)
    result = agent.process("ayuda")
    assert result.agent_action == "reply"
    assert result.response_text.startswith("Puedes consultarme sobre:")


def test_reply_for_data_request_is_not_passed_through():
    """Pedido con pinta de datos sin clasificador → ambiguous por keyword fallback."""
    llm = FakeLLMProvider()
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("cuantos cabos masculinos hay")
    assert result.agent_action == "ambiguous"


def test_reply_result_total_is_flagged_even_without_data_request_words():
    """Referencias de follow-up sin contexto → ambiguous en keyword fallback."""
    llm = FakeLLMProvider()
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("resultado anterior")
    assert result.agent_action == "ambiguous"
    assert "Resultado: total: 0" not in result.response_text


def test_reply_for_data_request_cannot_fabricate_data():
    """Reply para un pedido de datos → copy fijo; datos inventados no pasan.

    Aunque el LLM elija reply con payload inventado para un pedido de datos,
    `_handle_reply` ignora todo salvo response_type: la respuesta es el copy
    fijo y ningún texto ni dato del LLM llega al usuario.
    """
    llm = FakeLLMProvider(responses={
        "cuantos medicos tengo en total": (
            '{"tool": "reply", "params": {"response_type": "help", '
            '"texto_inventado": "Resultado: total: 0"}, "confidence": 0.9}'
        ),
    })
    agent = _make_llm_first_agent(llm)

    result = agent.process("cuantos medicos tengo en total")

    assert result.agent_action == "reply"
    assert result.response_text.startswith("Puedes consultarme sobre:")
    assert "Resultado: total: 0" not in result.response_text
