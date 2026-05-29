from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionState, SessionStore
from backend.app.application.telegram.types import AgentResult


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
