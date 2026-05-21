from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionState, SessionStore
from backend.app.application.telegram.types import AgentResult


def test_calendar_month_followup_reuses_previous_assignment_query():
    store = SessionStore(ttl_seconds=3600)
    agent = ConversationalAgent(
        llm=FakeLLMProvider(),
        router=IntentRouter(),
        session_store=store,
    )

    agent._remember_result(
        "tg-user",
        AgentResult(
            response_text="Resultado: total: 79",
            agent_action="query",
            tool_result={"data": {"columns": ["total"], "rows": [{"total": 79}]}},
        ),
        query_type="count_assigned_doctors_by_month",
        params={"year": 2026, "month": 8},
    )

    query = agent._calendar_followup_query_intent("y el de julio", "tg-user")

    assert query == (
        "count_assigned_doctors_by_month",
        {"year": 2026, "month": 7},
    )
    state = store.get("tg-user")
    assert state is not None
    assert state.last_domain == "calendar_assignments"
    assert state.last_period == {"year": 2026, "month": 8}
    assert state.last_subject == "assigned_doctors"


def test_session_store_persists_operational_context_fields():
    store = SessionStore(ttl_seconds=3600)
    store.set(
        "tg-user",
        SessionState(
            last_query_type="count_doctors_total",
            last_domain="doctors",
            last_period={"year": 2026, "month": 7},
            last_subject="doctor_count",
        ),
    )

    retrieved = store.get("tg-user")

    assert retrieved is not None
    assert retrieved.last_domain == "doctors"
    assert retrieved.last_period == {"year": 2026, "month": 7}
    assert retrieved.last_subject == "doctor_count"
