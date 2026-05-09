"""Tests for compound query detection (rank + sex, rank + area, etc.)."""
import pytest
from datetime import datetime, timezone

from backend.app.application.telegram.agent import ConversationalAgent, _count_filter_dims
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.infrastructure.db.models.catalogs import RankModel, ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — _count_filter_dims
# ═══════════════════════════════════════════════════════════════════════════


def test_count_filter_dims_empty():
    assert _count_filter_dims("") == 0


def test_count_filter_dims_single():
    assert _count_filter_dims("rank_id=3, rank_name='pasante'") == 1


def test_count_filter_dims_compound_rank_sex():
    assert _count_filter_dims("rank_id=3, rank_name='pasante', sex='female'") == 2


def test_count_filter_dims_compound_rank_area():
    assert _count_filter_dims("rank_id=3, area_id=5") == 2


def test_count_filter_dims_date_only():
    assert _count_filter_dims("date=2026-05-09") == 1


# ═══════════════════════════════════════════════════════════════════════════
# EntityResolver sex detection tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def resolver_with_ranks(db_session):
    """EntityResolver with ranks seeded for detection."""
    now = datetime.now(timezone.utc)
    ranks = [
        RankModel(id="11111111-1111-1111-1111-111111111111", name="Cabo", normalized_name="cabo", abbreviation="CBO", created_at=now, updated_at=now),
        RankModel(id="22222222-2222-2222-2222-222222222222", name="Sargento", normalized_name="sargento", abbreviation="SGT", created_at=now, updated_at=now),
        RankModel(id="33333333-3333-3333-3333-333333333333", name="Pasante", normalized_name="pasante", abbreviation="PST", created_at=now, updated_at=now),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()
    return EntityResolver(session=db_session)


def test_pre_process_detects_rank_and_sex(resolver_with_ranks):
    """'cuantos pasantes femeninos' → rank + sex detected."""
    result = resolver_with_ranks.pre_process("cuantos pasantes femeninos tenemos")
    hints = result["hints"]
    assert "rank_name='pasante'" in hints
    assert "sex='female'" in hints


def test_pre_process_detects_mujeres(resolver_with_ranks):
    """'cuantas mujeres' → sex detected."""
    result = resolver_with_ranks.pre_process("cuantas mujeres hay en total")
    assert "sex='female'" in result["hints"]


def test_pre_process_detects_hombres(resolver_with_ranks):
    """'cuantos hombres' → sex detected."""
    result = resolver_with_ranks.pre_process("dame la lista de hombres")
    assert "sex='male'" in result["hints"]


def test_pre_process_detects_masculinos(resolver_with_ranks):
    """'cuantos masculinos' → sex detected."""
    result = resolver_with_ranks.pre_process("cuantos masculinos tenemos")
    assert "sex='male'" in result["hints"]


# ═══════════════════════════════════════════════════════════════════════════
# Integration: compound query routes to QueryExecutor
# ═══════════════════════════════════════════════════════════════════════════


def test_compound_query_triggers_fallback(db_session):
    """When entity hints have >=2 dims, agent skips LLM and uses QueryExecutor."""
    now = datetime.now(timezone.utc)
    # Seed ranks
    ranks = [
        RankModel(id="11111111-1111-1111-1111-111111111111", name="Pasante", normalized_name="pasante", abbreviation="PST", created_at=now, updated_at=now),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()

    # Agent with EntityResolver + QueryExecutor
    sql_llm = FakeLLMProvider(responses={
        "pasantes femeninos": "SELECT 'Dra. García' AS medico, 'Pasante' AS rango, 'female' AS sexo LIMIT 100",
    })
    router = IntentRouter()
    router.set_session(db_session)
    query_exec = QueryExecutor(db_session, sql_llm)
    entity_resolver = EntityResolver(session=db_session)
    agent = ConversationalAgent(
        llm=FakeLLMProvider(responses={}),  # not used — compound skips LLM
        router=router,
        query_executor=query_exec,
        entity_resolver=entity_resolver,
    )

    result = agent.process("cuantos pasantes femeninos tenemos")

    # Must go to QueryExecutor (query_db action), not the LLM intent router
    assert result.agent_action == "query_db", (
        f"Expected query_db, got {result.agent_action}: {result.response_text[:200]}"
    )


def test_single_filter_still_uses_llm(db_session):
    """'cuantos pasantes' (single filter) → normal LLM intent routing."""
    now = datetime.now(timezone.utc)
    ranks = [
        RankModel(id="11111111-1111-1111-1111-111111111111", name="Pasante", normalized_name="pasante", abbreviation="PST", created_at=now, updated_at=now),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()

    entity_resolver = EntityResolver(session=db_session)
    # LLM returns a query action for single filter
    llm = FakeLLMProvider(responses={
        "cuantos pasantes hay": '{"action": "query", "query_type": "count_by_specific_rank", "params": {"rank": "pasante"}, "confidence": 0.9}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm, router=router,
        entity_resolver=entity_resolver,
    )

    result = agent.process("cuantos pasantes hay")
    # Single filter → normal router path (query action)
    assert result.agent_action == "query", (
        f"Expected query, got {result.agent_action}: {result.response_text[:200]}"
    )
