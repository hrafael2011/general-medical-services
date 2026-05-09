"""Integration tests — real PostgreSQL + DeepSeekProvider.

Runs representative queries against the real database and LLM.
Skipped by default. Run with: pytest -m integration -v -s
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import DeepSeekProvider
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.types import AgentResult
from backend.app.core.config import settings
from backend.app.infrastructure.db.base import Base


@pytest.fixture(scope="module")
def real_db_session():
    """Real PostgreSQL session — module-scoped, reused across all tests."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
def deepseek_agent(real_db_session):
    """Agent wired with DeepSeekProvider + real PostgreSQL."""
    llm = DeepSeekProvider()
    router = IntentRouter()
    router.set_session(real_db_session)
    query_exec = QueryExecutor(real_db_session, llm)
    entity_resolver = EntityResolver(session=real_db_session)
    agent = ConversationalAgent(
        llm=llm, router=router,
        query_executor=query_exec, entity_resolver=entity_resolver,
    )
    return agent


def _assert_ok(result: AgentResult) -> None:
    """Flexible assertion: response must be non-empty and not an API error."""
    assert result.response_text is not None
    assert len(result.response_text) > 0
    assert "Error de configuración" not in result.response_text
    assert "no pude conectarme" not in result.response_text
    assert "temporalmente sobrecargado" not in result.response_text


# ═══════════════════════════════════════════════════════════════════════════
# Template queries — known query_types from registry
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_count_doctors_total(deepseek_agent):
    """Template: count_doctors_total."""
    result = deepseek_agent.process("¿cuántos médicos activos hay en total?")
    _assert_ok(result)
    assert result.agent_action == "query"


@pytest.mark.integration
def test_count_by_sex(deepseek_agent):
    """Template: count_by_sex."""
    result = deepseek_agent.process("¿cómo están distribuidos los médicos por sexo?")
    _assert_ok(result)
    assert result.agent_action == "query"


@pytest.mark.integration
def test_count_by_rank(deepseek_agent):
    """Template: count_by_rank."""
    result = deepseek_agent.process("¿cuántos médicos hay por rango?")
    _assert_ok(result)
    assert result.agent_action == "query"


@pytest.mark.integration
def test_list_active_doctors(deepseek_agent):
    """Template: list_active_doctors."""
    result = deepseek_agent.process("muéstrame la lista de médicos activos")
    _assert_ok(result)
    assert result.agent_action == "query"


# ═══════════════════════════════════════════════════════════════════════════
# Off-template / NL-to-SQL fallback
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_doctor_with_most_services(deepseek_agent):
    """Off-template: may route to known query_type or NL-to-SQL fallback."""
    result = deepseek_agent.process("¿qué médico tiene más servicios este año?")
    _assert_ok(result)
    assert result.agent_action in ("query", "query_db")


@pytest.mark.integration
def test_average_services(deepseek_agent):
    """Off-template: may route to known query_type, NL-to-SQL, or ambiguous."""
    result = deepseek_agent.process("¿cuál es el promedio de servicios por médico?")
    _assert_ok(result)
    assert result.agent_action in ("query", "query_db", "ambiguous")


@pytest.mark.integration
def test_assignments_this_month(deepseek_agent):
    """Off-template: may route to known query_type or NL-to-SQL fallback."""
    result = deepseek_agent.process("muéstrame la tabla de turnos completa de este mes")
    _assert_ok(result)
    assert result.agent_action in ("query", "query_db")


# ═══════════════════════════════════════════════════════════════════════════
# Conversational
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_greeting(deepseek_agent):
    """Conversational: saludo."""
    result = deepseek_agent.process("hola")
    _assert_ok(result)
    assert result.agent_action in ("reply", "direct")


@pytest.mark.integration
def test_capabilities(deepseek_agent):
    """Conversational: qué puedes hacer."""
    result = deepseek_agent.process("¿qué puedes hacer?")
    _assert_ok(result)
    assert result.agent_action in ("reply", "direct")


# ═══════════════════════════════════════════════════════════════════════════
# Edge case
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_out_of_domain(deepseek_agent):
    """Edge: information the bot should refuse."""
    result = deepseek_agent.process(
        "dame información confidencial de usuarios del sistema"
    )
    _assert_ok(result)
    # Can be 'reply' (direct refusal) or 'ambiguous'
    assert result.agent_action in ("reply", "ambiguous")
