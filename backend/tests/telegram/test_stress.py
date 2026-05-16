"""Stress tests for the conversational agent — concurrency and load."""
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.query_executor import QueryExecutor


@pytest.fixture
def stress_agent(db_session, sqlite_registry):
    """Agent with FakeLLMProvider for fast stress testing."""
    responses = {
        "medicos activos": (
            '{"action": "query", "query_type": "count_doctors_total", "params": {}}'
        ),
        "por sexo": (
            '{"action": "query", "query_type": "count_by_sex", "params": {}}'
        ),
        "por rango": (
            '{"action": "query", "query_type": "count_by_rank", "params": {}}'
        ),
        "lista": (
            '{"action": "query", "query_type": "list_active_doctors", "params": {}}'
        ),
        "sargentos": (
            '{"action": "query", "query_type": "count_by_specific_rank", '
            '"params": {"rank": "sargento"}}'
        ),
        "cabos": (
            '{"action": "query", "query_type": "count_by_specific_rank", '
            '"params": {"rank": "cabo"}}'
        ),
        "resumen operativo": (
            '{"action": "query", "query_type": "operational_summary", '
            '"params": {"year": 2026, "month": 5}}'
        ),
        "trabajan hoy": (
            '{"action": "query", "query_type": "doctors_working_date", '
            '"params": {"date": "2026-05-09"}}'
        ),
        "hola": (
            '{"action": "reply", "response_text": "Hola, soy el asistente de turnos medicos."}'
        ),
        "gracias": (
            '{"action": "reply", "response_text": "De nada, estoy para ayudarte."}'
        ),
    }
    # Seed a doctor so that count queries return non-empty results
    from datetime import datetime as _dt, UTC as _UTC
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    if not db_session.query(DoctorModel).first():
        db_session.add(DoctorModel(
            id="00000000-0000-0000-0000-000000000001",
            name="Dr. Stress Test",
            normalized_name="dr. stress test",
            sex="male",
            active=True,
            service_active=True,
            availability_mode="monthly",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            created_at=_dt.now(_UTC),
            updated_at=_dt.now(_UTC),
        ))
        db_session.commit()

    llm = FakeLLMProvider(responses=responses)
    router = IntentRouter(registry=sqlite_registry)
    router.set_session(db_session)
    query_exec = QueryExecutor(db_session, llm)
    entity_resolver = EntityResolver(session=db_session)
    agent = ConversationalAgent(
        llm=llm, router=router,
        query_executor=query_exec, entity_resolver=entity_resolver,
    )
    return agent


def test_concurrent_10_queries(stress_agent):
    """10 concurrent queries should all succeed without errors."""
    questions = [
        "cuantos medicos activos hay",
        "como estan distribuidos por sexo",
        "cuantos hay por rango",
        "dame la lista de activos",
        "cuantos sargentos hay",
        "cuantos cabos hay",
        "cual es el resumen operativo de mayo",
        "que medicos trabajan hoy",
        "hola",
        "gracias",
    ]

    def ask(q):
        return stress_agent.process(q)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(ask, q) for q in questions]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 10
    for r in results:
        assert r.response_text is not None
        assert len(r.response_text) > 0
        # No API errors in any response
        for err in (
            "Error de configuracion",
            "no pude conectarme",
            "temporalmente sobrecargado",
        ):
            assert err not in r.response_text.lower()


def test_repeated_same_query_consistent(stress_agent):
    """20 repeated identical queries should all succeed."""
    def ask():
        return stress_agent.process("cuantos medicos activos hay")

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(ask) for _ in range(20)]
        results = [f.result() for f in as_completed(futures)]

    assert len(results) == 20
    for r in results:
        assert r.response_text is not None
        assert len(r.response_text) > 0
        assert r.agent_action in ("query", "query_db"), (
            f"Expected query or query_db, got {r.agent_action}: {r.response_text[:100]}"
        )
