from backend.app.application.telegram.conversation_contract import (
    CONVERSATION_CONTRACT,
    resolve_system_concept,
)
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider


def test_contract_defines_operational_terms_for_common_telegram_language():
    assert resolve_system_concept("disponible").canonical == "doctor_available_for_service"
    assert resolve_system_concept("de servicio").canonical == "calendar_assignment"
    assert resolve_system_concept("incluido en calendario").canonical == "calendar_participant"
    assert resolve_system_concept("ranking").canonical == "mission_ranking"


def test_contract_distinguishes_approved_and_draft_calendars():
    approved = resolve_system_concept("aprobado")
    draft = resolve_system_concept("borrador")

    assert approved.canonical == "approved_calendar"
    assert draft.canonical == "draft_calendar"
    assert "oficial" in approved.response_rule.lower()
    assert "borrador" in draft.response_rule.lower()


def test_agent_prompt_includes_conversation_contract():
    agent = ConversationalAgent(llm=FakeLLMProvider(), router=IntentRouter())

    prompt = agent._build_system_prompt(user_info=None)

    for concept in CONVERSATION_CONTRACT:
        assert concept.canonical in prompt
    assert "No inventes conteos" in prompt
