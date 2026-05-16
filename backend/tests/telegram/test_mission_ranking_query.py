import uuid
from datetime import UTC, datetime

from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import (
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
)


def test_mission_ranking_query_uses_current_schema(db_session):
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dr. Ranking Uno",
        normalized_name="dr. ranking uno",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=now,
        updated_at=now,
    )
    ranking = MissionCandidateRankingModel(
        id=str(uuid.uuid4()),
        year=2026,
        month=8,
        calendar_version_id=None,
        generated_at=now,
        created_by="tester",
    )
    entry = MissionCandidateRankingEntryModel(
        id=str(uuid.uuid4()),
        mission_candidate_ranking_id=ranking.id,
        doctor_id=doctor.id,
        ranking_position=1,
        total_load_score=0.5,
        monthly_service_load=0.0,
        recent_service_load=0.0,
        monthly_mission_load=0.0,
        eligible=True,
        reasons={},
        warnings=[],
    )
    db_session.add_all([doctor, ranking, entry])
    db_session.commit()

    router = IntentRouter()
    router.set_session(db_session)

    result = router.handle(
        action="query",
        query_type="mission_ranking",
        params={"year": 2026, "month": 8},
        user_message="ranking de misiones agosto 2026",
    )

    assert "Dr. Ranking Uno" in result.response_text
    assert "1" in result.response_text
    assert "No pude encontrar" not in result.response_text


def test_agent_routes_mission_ranking_month_without_llm(db_session):
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dr. Ranking Natural",
        normalized_name="dr. ranking natural",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=now,
        updated_at=now,
    )
    ranking = MissionCandidateRankingModel(
        id=str(uuid.uuid4()),
        year=2026,
        month=8,
        calendar_version_id=None,
        generated_at=now,
        created_by="tester",
    )
    entry = MissionCandidateRankingEntryModel(
        id=str(uuid.uuid4()),
        mission_candidate_ranking_id=ranking.id,
        doctor_id=doctor.id,
        ranking_position=1,
        total_load_score=0.5,
        monthly_service_load=0.0,
        recent_service_load=0.0,
        monthly_mission_load=0.0,
        eligible=True,
        reasons={},
        warnings=[],
    )
    db_session.add_all([doctor, ranking, entry])
    db_session.commit()

    llm = FakeLLMProvider(responses={
        "ranking": '{"action": "reply", "response_text": "Resultado: total: 0"}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(llm=llm, router=router)

    result = agent.process("cuales son los 3 medicos que tengo en el ranking de misiones agosto 2026")

    assert result.agent_action == "query"
    assert "Dr. Ranking Natural" in result.response_text
    assert llm.calls == []
