"""Tests for reply content guard."""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.types import AgentResult


class ReplyGuardRouterStub(IntentRouter):
    """Stub that returns ok for any handle() call — we only test reply path."""
    def handle(self, **kwargs):
        return AgentResult(response_text="ok")


class SequentialLLM:
    name = "sequential"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_complete(self, messages, temperature=0.1, json_mode=False):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        return self.responses.pop(0)


def test_reply_with_hallucinated_data_is_flagged():
    """Reply containing invented doctor names should be replaced with generic."""
    llm = FakeLLMProvider(responses={
        "datos": (
            '{"action": "reply", "response_text": "Tienes 15 doctores activos '
            'incluyendo al Dr. Perez y la Dra. Garcia."}'
        ),
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("dame datos")
    assert "Perez" not in result.response_text
    assert "Garcia" not in result.response_text


def test_valid_reply_passes_through():
    """Generic reply without invented data passes through."""
    llm = FakeLLMProvider(responses={
        "ayuda": (
            '{"action": "reply", "response_text": "Puedo consultar medicos, '
            'generar reportes y exportar datos."}'
        ),
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("ayuda")
    assert "Puedo consultar" in result.response_text


def test_reply_with_numbers_is_flagged():
    """Reply containing specific counts should be replaced."""
    llm = FakeLLMProvider(responses={
        "cuantos": (
            '{"action": "reply", "response_text": '
            '"Actualmente hay 226 medicos en el sistema."}'
        ),
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("cuantos hay")
    assert "226" not in result.response_text


def test_reply_with_singular_doctor_is_flagged():
    """Reply with singular 'doctor' and count should also be flagged."""
    llm = FakeLLMProvider(responses={
        "sing": '{"action": "reply", "response_text": "Hay 1 doctor activo."}',
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("cuantos doctores")
    assert "doctor" not in result.response_text.lower() or "Puedo ayudarte" in result.response_text


def test_reply_for_data_request_is_not_passed_through():
    """A data-looking user request cannot be answered through action=reply."""
    llm = FakeLLMProvider(responses={
        "cabos": '{"action": "reply", "response_text": "Claro, hay varios cabos."}',
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("cuantos cabos masculinos hay")
    assert result.agent_action == "ambiguous"
    assert "no verificada" in result.response_text.lower()


def test_reply_result_total_is_flagged_even_without_data_request_words():
    """Direct replies like 'Resultado: total: 0' are never trusted as chat text."""
    llm = FakeLLMProvider(responses={
        "resultado": '{"action": "reply", "response_text": "Resultado: total: 0"}',
    })
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("resultado anterior")

    assert result.agent_action == "reply"
    assert "Resultado: total: 0" not in result.response_text
    assert "Puedo ayudarte" in result.response_text


def test_data_request_reply_uses_query_executor_when_available(db_session):
    """If the LLM tries reply for a data request, fallback must be grounded."""
    llm = SequentialLLM([
        '{"action": "reply", "response_text": "Resultado: total: 0"}',
        "SELECT COUNT(*) AS total FROM doctors",
        '{"verdict": "correct", "reason": "OK"}',
    ])
    agent = ConversationalAgent(
        llm=llm,
        router=ReplyGuardRouterStub(),
        query_executor=QueryExecutor(db_session, llm),
    )

    result = agent.process("cuantos medicos tengo en total")

    assert result.agent_action == "query_db"
    assert result.tool_result is not None
    assert result.tool_result["source"] == "nl_to_sql"
    assert "sql" in result.tool_result
