"""Tests for reply behavior in LLM-first architecture."""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_classifier import IntentClassifier
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.types import AgentResult


class ReplyGuardRouterStub(IntentRouter):
    """Stub that returns ok for any handle() call."""
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


def test_valid_reply_passes_through():
    """Generic reply without data passes through directly."""
    llm = FakeLLMProvider(responses={
        "ayuda": (
            '{"domain": "general", "action": "reply", "metric": null, '
            '"query_type": null, "params": {}, "confidence": 0.9, '
            '"response_text": "Puedo consultar medicos, '
            'generar reportes y exportar datos.", "format": null}'
        ),
    })
    classifier = IntentClassifier(llm)
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub(), intent_classifier=classifier)
    result = agent.process("ayuda")
    assert "Puedo consultar" in result.response_text


def test_reply_for_data_request_is_not_passed_through():
    """A data-looking user request is classified as ambiguous by keyword fallback."""
    llm = FakeLLMProvider()
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("cuantos cabos masculinos hay")
    assert result.agent_action == "ambiguous"


def test_reply_result_total_is_flagged_even_without_data_request_words():
    """Follow-up references without context default to ambiguous in keyword fallback."""
    llm = FakeLLMProvider()
    agent = ConversationalAgent(llm=llm, router=ReplyGuardRouterStub())
    result = agent.process("resultado anterior")
    assert result.agent_action == "ambiguous"
    assert "Resultado: total: 0" not in result.response_text


def test_data_request_reply_uses_query_executor_when_available(db_session):
    """If the LLM tries reply for a data request, fallback must be grounded."""
    llm = SequentialLLM([
        '{"domain": "general", "action": "reply", "metric": null, '
        '"query_type": null, "params": {}, "confidence": 0.9, '
        '"response_text": "Resultado: total: 0", "format": null}',
        "SELECT COUNT(*) AS total FROM doctors",
        '{"verdict": "correct", "reason": "OK"}',
    ])
    classifier = IntentClassifier(llm)
    agent = ConversationalAgent(
        llm=llm,
        router=ReplyGuardRouterStub(),
        query_executor=QueryExecutor(db_session, llm),
        intent_classifier=classifier,
    )

    result = agent.process("cuantos medicos tengo en total")

    assert result.agent_action == "query_db"
    assert result.tool_result is not None
    assert result.tool_result["source"] == "nl_to_sql"
    assert "sql" in result.tool_result
