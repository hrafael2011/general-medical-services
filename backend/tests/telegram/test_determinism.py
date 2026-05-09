"""Tests for deterministic intent classification."""
import pytest
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.types import AgentResult


class DeterminismRouterStub(IntentRouter):
    """Stub that records actions for determinism testing."""
    def handle(self, **kwargs):
        return AgentResult(response_text="ok")


def test_same_input_produces_same_action():
    """Same input should produce same action with temperature=0."""
    llm = FakeLLMProvider(responses={
        "medicos": '{"action": "query", "response_text": "Hay 10 medicos activos."}',
    })
    agent = ConversationalAgent(llm=llm, router=DeterminismRouterStub())

    result1 = agent.process("cuantos medicos hay")
    result2 = agent.process("cuantos medicos hay")

    assert result1.agent_action == result2.agent_action
    assert result1.response_text == result2.response_text
