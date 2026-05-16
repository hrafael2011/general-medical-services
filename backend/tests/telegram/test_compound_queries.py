"""Tests for compound query detection (rank + sex, rank + area, etc.)."""
import logging
from datetime import UTC, datetime

import pytest

from backend.app.application.telegram.agent import ConversationalAgent, _count_filter_dims
from backend.app.application.telegram.doctor_query_service import DoctorQueryService
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionStore
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.infrastructure.db.models.catalogs import RankModel
from backend.app.infrastructure.db.models.doctors import DoctorModel


def _rank_model(rank_id: str, name: str, normalized_name: str, abbreviation: str, now):
    return RankModel(
        id=rank_id,
        name=name,
        normalized_name=normalized_name,
        abbreviation=abbreviation,
        created_at=now,
        updated_at=now,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Unit tests — _count_filter_dims
# ═══════════════════════════════════════════════════════════════════════════


def test_count_filter_dims_empty():
    assert _count_filter_dims("") == 0


def test_count_filter_dims_single():
    assert _count_filter_dims("rank_id=3, rank='pasante'") == 1


def test_count_filter_dims_compound_rank_sex():
    assert _count_filter_dims("rank_id=3, rank='pasante', sex='female'") == 2


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
    now = datetime.now(UTC)
    ranks = [
        _rank_model("11111111-1111-1111-1111-111111111111", "Cabo", "cabo", "CBO", now),
        _rank_model(
            "22222222-2222-2222-2222-222222222222",
            "Sargento",
            "sargento",
            "SGT",
            now,
        ),
        _rank_model(
            "33333333-3333-3333-3333-333333333333",
            "Pasante",
            "pasante",
            "PST",
            now,
        ),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()
    return EntityResolver(session=db_session)


def test_pre_process_detects_rank_and_sex(resolver_with_ranks):
    """'cuantos pasantes femeninos' → rank + sex detected."""
    result = resolver_with_ranks.pre_process("cuantos pasantes femeninos tenemos")
    hints = result["hints"]
    assert "rank='pasante'" in hints
    assert "sex='female'" in hints


@pytest.mark.parametrize(
    ("message", "rank"),
    [
        ("exporta solo los cabos masculinos", "cabo"),
        ("exporta solo los cabos massulino", "cabo"),
        ("exporta la informacion en pdf de todos sargento masculinos", "sargento"),
        ("exporta la informacion en pdf de todos sargento masuculinos", "sargento"),
        ("cuantos masculino y femeninos tienen el rango de pasante", "pasante"),
        ("cuantos masuclino y femeninos tienen el rango de pasante", "pasante"),
    ],
)
def test_pre_process_detects_real_compound_examples(resolver_with_ranks, message, rank):
    """Real encargado phrasing → rank + sex dimensions are detected."""
    result = resolver_with_ranks.pre_process(message)
    hints = result["hints"]
    assert f"rank='{rank}'" in hints
    assert "sex=" in hints
    assert _count_filter_dims(hints) >= 2


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


@pytest.mark.parametrize("word", ["masuclino", "massulino", "masuculinos", "masuclinos"])
def test_pre_process_detects_common_masculino_typos(resolver_with_ranks, word):
    """Common misspellings of masculino still map to doctors.sex='male'."""
    result = resolver_with_ranks.pre_process(f"exporta cabos {word}")
    assert "rank='cabo'" in result["hints"]
    assert "sex='male'" in result["hints"]


# ═══════════════════════════════════════════════════════════════════════════
# Integration: compound query routes to QueryExecutor
# ═══════════════════════════════════════════════════════════════════════════


def test_compound_query_triggers_fallback(db_session):
    """When entity hints have >=2 dims, agent skips LLM and uses QueryExecutor."""
    now = datetime.now(UTC)
    # Seed ranks
    ranks = [
        _rank_model(
            "11111111-1111-1111-1111-111111111111",
            "Pasante",
            "pasante",
            "PST",
            now,
        ),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()

    # Agent with EntityResolver + QueryExecutor
    sql_llm = FakeLLMProvider(responses={
        "pasantes femeninos": (
            "SELECT 'Dra. García' AS medico, 'Pasante' AS rango, "
            "'female' AS sexo LIMIT 100"
        ),
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


def test_compound_doctor_query_uses_deterministic_service(db_session):
    """Rank + sex filters are answered by DoctorQueryService before NL-to-SQL."""
    now = datetime.now(UTC)
    rank = RankModel(
        id="11111111-1111-1111-1111-111111111111",
        name="Pasante",
        normalized_name="pasante",
        abbreviation="PST",
        created_at=now,
        updated_at=now,
    )
    db_session.add(rank)
    db_session.add_all([
        DoctorModel(
            id="doc-male-1",
            name="Dr. Pasante Uno",
            normalized_name="dr. pasante uno",
            sex="male",
            active=True,
            service_active=True,
            availability_mode="monthly",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            rank_id=rank.id,
            created_at=now,
            updated_at=now,
        ),
        DoctorModel(
            id="doc-female-1",
            name="Dra. Pasante Dos",
            normalized_name="dra. pasante dos",
            sex="female",
            active=True,
            service_active=True,
            availability_mode="monthly",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            rank_id=rank.id,
            created_at=now,
            updated_at=now,
        ),
    ])
    db_session.commit()

    llm = FakeLLMProvider(responses={})
    session_store = SessionStore()
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=QueryExecutor(db_session, llm),
        entity_resolver=EntityResolver(session=db_session),
        doctor_query_service=DoctorQueryService(db_session),
        session_store=session_store,
    )

    result = agent.process(
        "cuantos masculino y femeninos tienen el rango de pasante",
        telegram_user_id="tg-context",
    )

    assert result.agent_action == "query"
    assert result.tool_name == "doctor_query_service"
    assert "Masculino" in result.response_text
    assert "Femenino" in result.response_text
    assert result.tool_entities["requested_filters"] == {
        "rank": "pasante",
        "sex": ["male", "female"],
    }
    assert result.tool_entities["applied_filters"] == result.tool_entities["requested_filters"]
    assert set(result.tool_result["validated_filters"]) == {"rank", "sex"}
    assert llm.calls == []
    state = session_store.get("tg-context")
    assert state is not None
    assert state.last_filters == {"rank": "pasante", "sex": ["male", "female"]}
    assert state.last_tool_name == "doctor_query_service"
    assert state.last_agent_action == "query"

    list_result = agent.process("dame la lista de pasante masculinos")

    assert list_result.agent_action == "query"
    assert list_result.tool_name == "doctor_query_service"
    assert "Dr. Pasante Uno" in list_result.response_text
    assert "Dra. Pasante Dos" not in list_result.response_text
    assert list_result.tool_entities["applied_filters"] == {
        "rank": "pasante",
        "sex": ["male"],
    }
    assert llm.calls == []

    pdf_result = agent.process("exporta la informacion en pdf de todos pasante masuculinos")

    assert pdf_result.agent_action == "export"
    assert pdf_result.tool_name == "doctor_query_service"
    assert pdf_result.document_bytes is not None
    assert len(pdf_result.document_bytes) > 100
    assert pdf_result.document_filename == "MEDICOS_FILTRADOS.pdf"
    assert pdf_result.tool_result["data"]["rows"][0]["name"] == "Dr. Pasante Uno"
    assert set(pdf_result.tool_result["validated_filters"]) == {"rank", "sex"}
    assert llm.calls == []

    excel_result = agent.process("exporta en excel todos pasante masculinos")

    assert excel_result.agent_action == "export"
    assert excel_result.document_bytes is not None
    assert excel_result.document_filename == "MEDICOS_FILTRADOS.xlsx"
    assert llm.calls == []


def test_compound_doctor_query_emits_observability_log(db_session, caplog):
    """Deterministic compound queries emit structured routing logs."""
    now = datetime.now(UTC)
    rank = RankModel(
        id="11111111-1111-1111-1111-111111111111",
        name="Cabo",
        normalized_name="cabo",
        abbreviation="CBO",
        created_at=now,
        updated_at=now,
    )
    db_session.add(rank)
    db_session.add(DoctorModel(
        id="doc-male-obs",
        name="Dr. Cabo Obs",
        normalized_name="dr. cabo obs",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        rank_id=rank.id,
        created_at=now,
        updated_at=now,
    ))
    db_session.commit()

    llm = FakeLLMProvider(responses={})
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=QueryExecutor(db_session, llm),
        entity_resolver=EntityResolver(session=db_session),
        doctor_query_service=DoctorQueryService(db_session),
    )

    with caplog.at_level(logging.INFO):
        result = agent.process("exporta cabos masculinos")

    assert result.agent_action == "export"
    events = [getattr(record, "telegram_event", None) for record in caplog.records]
    assert "doctor_query_route" in events
    assert "doctor_query_export_completed" in events
    assert "agent_route_completed" in events


def test_single_filter_still_uses_llm(db_session):
    """'cuantos pasantes' (single filter) → normal LLM intent routing."""
    now = datetime.now(UTC)
    ranks = [
        _rank_model(
            "11111111-1111-1111-1111-111111111111",
            "Pasante",
            "pasante",
            "PST",
            now,
        ),
    ]
    for r in ranks:
        db_session.add(r)
    db_session.commit()

    entity_resolver = EntityResolver(session=db_session)
    # LLM returns a query action for single filter
    llm = FakeLLMProvider(responses={
        "cuantos pasantes hay": (
            '{"action": "query", "query_type": "count_by_specific_rank", '
            '"params": {"rank": "pasante"}, "confidence": 0.9}'
        ),
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm, router=router,
        entity_resolver=entity_resolver,
    )

    result = agent.process("cuantos pasantes hay")
    # Single filter → router returns empty (no doctors seeded), fallback triggers
    # Since there's no query_executor in this test, we get a graceful message.
    assert result.agent_action in ("query", "direct"), (
        f"Expected query or direct, got {result.agent_action}: {result.response_text[:200]}"
    )


def test_followup_reuses_previous_rank_for_count_and_export(db_session):
    """Follow-ups like 'cuantos son femeninos' reuse the previous rank filter."""
    now = datetime.now(UTC)
    rank = _rank_model(
        "11111111-1111-1111-1111-111111111111",
        "Pasante",
        "pasante",
        "PST",
        now,
    )
    db_session.add(rank)
    db_session.add_all(
        [
            DoctorModel(
                id="doc-pasante-male-followup",
                name="Dr. Pasante Contexto",
                normalized_name="dr. pasante contexto",
                sex="male",
                active=True,
                service_active=True,
                availability_mode="monthly",
                participa_misiones=True,
                monthly_service_target=3,
                monthly_service_max=3,
                monthly_service_limit_mode="warn_only",
                rank_id=rank.id,
                created_at=now,
                updated_at=now,
            ),
            DoctorModel(
                id="doc-pasante-female-followup",
                name="Dra. Pasante Contexto",
                normalized_name="dra. pasante contexto",
                sex="female",
                active=True,
                service_active=True,
                availability_mode="monthly",
                participa_misiones=True,
                monthly_service_target=3,
                monthly_service_max=3,
                monthly_service_limit_mode="warn_only",
                rank_id=rank.id,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    llm = FakeLLMProvider(
        responses={
            "cuantos pasantes tenemos": (
                '{"action": "query", "query_type": "count_by_specific_rank", '
                '"params": {"rank": "pasante"}, "confidence": 0.9}'
            ),
        }
    )
    session_store = SessionStore()
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=QueryExecutor(db_session, llm),
        entity_resolver=EntityResolver(session=db_session),
        doctor_query_service=DoctorQueryService(db_session),
        session_store=session_store,
    )

    first = agent.process("cuantos pasantes tenemos", telegram_user_id="tg-followup")
    second = agent.process("cuantos son femeninos?", telegram_user_id="tg-followup")
    third = agent.process("exportalo en pdf", telegram_user_id="tg-followup")

    assert first.agent_action == "query"
    assert second.tool_name == "doctor_query_service"
    assert second.response_text == "Resultado: total: 1"
    assert third.agent_action == "export"
    assert third.document_filename == "MEDICOS_FILTRADOS.pdf"
    assert third.tool_result["data"]["rows"] == [
        {"name": "Dra. Pasante Contexto", "sex": "female", "rank": "Pasante"}
    ]


def test_doctor_query_counts_same_name_distinct_ids(db_session):
    """Homonyms or sample duplicate names remain distinct when IDs differ."""
    now = datetime.now(UTC)
    rank = _rank_model(
        "11111111-1111-1111-1111-111111111111",
        "Sargento",
        "sargento",
        "SGT",
        now,
    )
    db_session.add(rank)
    db_session.add_all(
        [
            DoctorModel(
                id="doc-sargento-female-duplicate-name-1",
                name="Dra. Nombre Repetido",
                normalized_name="dra. nombre repetido",
                sex="female",
                active=True,
                service_active=True,
                availability_mode="monthly",
                participa_misiones=True,
                monthly_service_target=3,
                monthly_service_max=3,
                monthly_service_limit_mode="warn_only",
                rank_id=rank.id,
                created_at=now,
                updated_at=now,
            ),
            DoctorModel(
                id="doc-sargento-female-duplicate-name-2",
                name="Dra. Nombre Repetido",
                normalized_name="dra. nombre repetido-2",
                sex="female",
                active=True,
                service_active=True,
                availability_mode="monthly",
                participa_misiones=True,
                monthly_service_target=3,
                monthly_service_max=3,
                monthly_service_limit_mode="warn_only",
                rank_id=rank.id,
                created_at=now,
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    router = IntentRouter()
    router.set_session(db_session)
    llm = FakeLLMProvider(responses={})
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=QueryExecutor(db_session, llm),
        entity_resolver=EntityResolver(session=db_session),
        doctor_query_service=DoctorQueryService(db_session),
    )

    count_result = agent.process("cuantas sargentos femeninas tenemos")
    list_result = agent.process("dame listado de sargentos femeninas")

    assert count_result.response_text == "Resultado: total: 2"
    assert "Se encontraron 2 resultados" in list_result.response_text
    assert list_result.tool_result["possible_duplicate_names"] == [
        {"name": "Dra. Nombre Repetido", "count": 2}
    ]


def test_real_chat_followups_do_not_jump_between_ranks(db_session):
    """Regression for cabos/sargentos follow-ups from the Telegram transcript."""
    now = datetime.now(UTC)
    cabo = _rank_model(
        "11111111-1111-1111-1111-111111111111",
        "Cabo",
        "cabo",
        "CBO",
        now,
    )
    sargento = _rank_model(
        "22222222-2222-2222-2222-222222222222",
        "Sargento",
        "sargento",
        "SGT",
        now,
    )
    db_session.add_all([cabo, sargento])
    doctors = [
        ("cabo-female-1", "Dra. Cabo Una", "female", cabo.id),
        ("cabo-female-2", "Dra. Cabo Dos", "female", cabo.id),
        ("cabo-male-1", "Dr. Cabo Uno", "male", cabo.id),
        ("sargento-female-1", "Dra. Sargento Una", "female", sargento.id),
    ]
    for doctor_id, name, sex, rank_id in doctors:
        db_session.add(
            DoctorModel(
                id=doctor_id,
                name=name,
                normalized_name=name.lower(),
                sex=sex,
                active=True,
                service_active=True,
                availability_mode="monthly",
                participa_misiones=True,
                monthly_service_target=3,
                monthly_service_max=3,
                monthly_service_limit_mode="warn_only",
                rank_id=rank_id,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()

    llm = FakeLLMProvider(responses={})
    session_store = SessionStore()
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=QueryExecutor(db_session, llm),
        entity_resolver=EntityResolver(session=db_session),
        doctor_query_service=DoctorQueryService(db_session),
        session_store=session_store,
    )

    cabos_female = agent.process(
        "Cuantos medicos Cabos femeninos hay ?",
        telegram_user_id="tg-real-chat",
    )
    cabos_male_followup = agent.process(
        "Y masculinos ?",
        telegram_user_id="tg-real-chat",
    )
    sargentos_female_list = agent.process(
        "Dame un listado de la sargentos femeninas",
        telegram_user_id="tg-real-chat",
    )
    sargentos_confirm = agent.process(
        "Son 2 o 1 femeninas ?",
        telegram_user_id="tg-real-chat",
    )

    assert cabos_female.response_text == "Resultado: total: 2"
    assert cabos_male_followup.response_text == "Resultado: total: 1"
    assert "Dra. Sargento Una" in sargentos_female_list.response_text
    assert sargentos_confirm.response_text == "Resultado: total: 1"
