import uuid
from datetime import UTC, datetime

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionStore
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
    MissionParticipantModel,
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
        whatsapp_phone="0000000000",
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
        whatsapp_phone="0000000000",
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
    agent = ConversationalAgent(llm=llm, router=router, session_store=SessionStore())

    result = agent.process(
        "cuales son los 3 medicos que tengo en el ranking de misiones agosto 2026"
    )

    assert result.agent_action == "query"
    assert "Dr. Ranking Natural" in result.response_text
    assert llm.calls == []


def test_active_missions_query_uses_current_schema(db_session):
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dra. Mision Activa",
        normalized_name="dra. mision activa",
        sex="female",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=now,
        updated_at=now,
    )
    mission = MissionAssignmentModel(
        id=str(uuid.uuid4()),
        mission_date=now.date(),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=1,
        location="Hospital Central",
        description="Apoyo operativo",
        source="manual",
        status="confirmed",
        created_by="tester",
        confirmed_by="tester",
        confirmed_at=now,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    participant = MissionParticipantModel(
        id=str(uuid.uuid4()),
        mission_assignment_id=mission.id,
        doctor_id=doctor.id,
        selection_source="manual",
        ranking_position=None,
        score=None,
        reasons={},
        warnings=[],
        created_at=now,
    )
    db_session.add_all([doctor, mission, participant])
    db_session.commit()

    router = IntentRouter()
    router.set_session(db_session)

    result = router.handle(
        action="query",
        query_type="list_active_missions",
        params={},
        user_message="cuales misiones estan activas",
    )

    assert result.agent_action == "query"
    assert "Hospital Central" in result.response_text
    assert "Dra. Mision Activa" in result.response_text
    assert "No pude encontrar" not in result.response_text


def test_agent_routes_active_missions_without_llm(db_session):
    now = datetime.now(UTC)
    mission = MissionAssignmentModel(
        id=str(uuid.uuid4()),
        mission_date=now.date(),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=0,
        location="Base Norte",
        description="Mision pendiente",
        source="manual",
        status="draft",
        created_by="tester",
        confirmed_by=None,
        confirmed_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db_session.add(mission)
    db_session.commit()

    llm = FakeLLMProvider(responses={
        "misiones": '{"action": "reply", "response_text": "No tengo acceso a misiones."}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(llm=llm, router=router, session_store=SessionStore())

    result = agent.process("cuales misiones estan activa")

    assert result.agent_action == "query"
    assert "Base Norte" in result.response_text
    assert "No tengo acceso" not in result.response_text
    assert llm.calls == []


def test_agent_filters_active_mission_followup_to_approved(db_session):
    now = datetime.now(UTC)
    confirmed = MissionAssignmentModel(
        id=str(uuid.uuid4()),
        mission_date=now.date(),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=0,
        location="Base Aprobada",
        description="Llegar temprano",
        source="manual",
        status="confirmed",
        created_by="tester",
        confirmed_by="tester",
        confirmed_at=now,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    draft = MissionAssignmentModel(
        id=str(uuid.uuid4()),
        mission_date=now.date(),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=0,
        location="Base Pendiente",
        description="Pendiente",
        source="manual",
        status="draft",
        created_by="tester",
        confirmed_by=None,
        confirmed_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db_session.add_all([confirmed, draft])
    db_session.commit()

    llm = FakeLLMProvider(responses={
        "aprobadas": '{"action": "ambiguous", "response_text": "Necesito contexto."}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(llm=llm, router=router, session_store=SessionStore())

    first = agent.process("cuales misiones estan activa", telegram_user_id="u-missions")
    followup = agent.process("cuales estan aprobadas ?", telegram_user_id="u-missions")

    assert first.agent_action == "query"
    assert followup.agent_action == "query"
    assert "Base Aprobada" in followup.response_text
    assert "Base Pendiente" not in followup.response_text
    assert llm.calls == []


def test_agent_resolves_responsibles_for_numbered_mission_followup(db_session):
    now = datetime.now(UTC)
    doctor_a = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dra. Responsable Uno",
        normalized_name="dra. responsable uno",
        sex="female",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=now,
        updated_at=now,
    )
    doctor_b = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dr. Responsable Dos",
        normalized_name="dr. responsable dos",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="monthly",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=now,
        updated_at=now,
    )
    mission = MissionAssignmentModel(
        id=str(uuid.uuid4()),
        mission_date=now.date(),
        mission_start_at=None,
        mission_end_at=None,
        participant_count=2,
        location="Base Compartida",
        description="Mision compartida",
        source="manual",
        status="confirmed",
        created_by="tester",
        confirmed_by="tester",
        confirmed_at=now,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    participants = [
        MissionParticipantModel(
            id=str(uuid.uuid4()),
            mission_assignment_id=mission.id,
            doctor_id=doctor_a.id,
            selection_source="manual",
            ranking_position=None,
            score=None,
            reasons={},
            warnings=[],
            created_at=now,
        ),
        MissionParticipantModel(
            id=str(uuid.uuid4()),
            mission_assignment_id=mission.id,
            doctor_id=doctor_b.id,
            selection_source="manual",
            ranking_position=None,
            score=None,
            reasons={},
            warnings=[],
            created_at=now,
        ),
    ]
    db_session.add_all([doctor_a, doctor_b, mission, *participants])
    db_session.commit()

    llm = FakeLLMProvider(responses={
        "responsable": '{"action": "reply", "response_text": "No tengo acceso."}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(llm=llm, router=router, session_store=SessionStore())

    agent.process("cuales misiones estan activa", telegram_user_id="u-responsibles")
    followup = agent.process(
        "cuales son los medicos responsable de la mision numero 1 del listado",
        telegram_user_id="u-responsibles",
    )

    assert followup.agent_action == "query"
    assert "Dra. Responsable Uno" in followup.response_text
    assert "Dr. Responsable Dos" in followup.response_text
    assert "No tengo acceso" not in followup.response_text
    assert llm.calls == []
