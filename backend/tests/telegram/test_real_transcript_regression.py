import uuid
from datetime import UTC, date, datetime

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.calendar_query_service import CalendarQueryService
from backend.app.application.telegram.doctor_query_service import DoctorQueryService
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionStore
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import RankModel, ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import (
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
)


def _now():
    return datetime.now(UTC)


def _rank(session, name: str, normalized_name: str):
    now = _now()
    rank = RankModel(
        id=str(uuid.uuid4()),
        name=name,
        normalized_name=normalized_name,
        abbreviation=name[:3].upper(),
        active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(rank)
    session.flush()
    return rank


def _doctor(session, *, name: str, sex: str, rank_id: str | None = None):
    now = _now()
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
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
    session.add(doctor)
    session.flush()
    return doctor


def _area(session):
    now = _now()
    area = ServiceAreaModel(
        id=str(uuid.uuid4()),
        code="REG",
        display_name="Regulación",
        load_weight=1,
        active=True,
        required_for_daily_coverage=True,
        created_at=now,
        updated_at=now,
    )
    session.add(area)
    session.flush()
    return area


def _calendar_assignment(session, *, year: int, month: int, status: str, day: int, doctor_id: str, area_id: str):
    now = _now()
    calendar = CalendarModel(
        id=str(uuid.uuid4()),
        year=year,
        month=month,
        status=status,
        created_at=now,
        updated_at=now,
        approved_at=now if status == "approved" else None,
    )
    session.add(calendar)
    session.flush()
    version = CalendarVersionModel(
        id=str(uuid.uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status=status,
        created_at=now,
        approved_at=now if status == "approved" else None,
    )
    session.add(version)
    session.flush()
    session.add(
        CalendarAssignmentModel(
            id=str(uuid.uuid4()),
            calendar_version_id=version.id,
            service_date=date(year, month, day),
            service_area_id=area_id,
            doctor_id=doctor_id,
            assignment_source="manual",
            created_at=now,
        )
    )
    session.flush()
    return version


def _ranking(session, *, year: int, month: int, doctor_id: str):
    now = _now()
    ranking = MissionCandidateRankingModel(
        id=str(uuid.uuid4()),
        year=year,
        month=month,
        calendar_version_id=None,
        generated_at=now,
        created_by="tester",
    )
    session.add(ranking)
    session.flush()
    session.add(
        MissionCandidateRankingEntryModel(
            id=str(uuid.uuid4()),
            mission_candidate_ranking_id=ranking.id,
            doctor_id=doctor_id,
            ranking_position=1,
            total_load_score=0.0,
            monthly_service_load=0.0,
            recent_service_load=0.0,
            monthly_mission_load=0.0,
            eligible=True,
            reasons={},
            warnings=[],
        )
    )
    session.flush()


def test_real_telegram_transcript_regression_core(db_session):
    cabo = _rank(db_session, "Cabo", "cabo")
    pasante = _rank(db_session, "Pasante", "pasante")
    cabo_female = _doctor(db_session, name="Dra. Cabo Transcript", sex="female", rank_id=cabo.id)
    cabo_male = _doctor(db_session, name="Dr. Cabo Transcript", sex="male", rank_id=cabo.id)
    _doctor(db_session, name="Dra. Pasante Transcript", sex="female", rank_id=pasante.id)
    area = _area(db_session)
    _calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        day=4,
        doctor_id=cabo_female.id,
        area_id=area.id,
    )
    _calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        day=4,
        doctor_id=cabo_male.id,
        area_id=area.id,
    )
    _ranking(db_session, year=2026, month=8, doctor_id=cabo_male.id)
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
        calendar_query_service=CalendarQueryService(db_session),
        session_store=SessionStore(),
    )

    assert agent.process("cuantos medicos femeninos tengo").response_text == "Resultado: total: 2"
    assert agent.process("cuantos medicos cabo tengo").response_text == "Resultado: total: 2"

    august = agent.process(
        "cuales son los medicos de servicio la primera semana de agosto 2026",
        telegram_user_id="tg-real-regression",
    )
    july = agent.process("ok entiendo y de julio ?", telegram_user_id="tg-real-regression")
    ranking = agent.process("cuales son los 3 medicos del ranking de misiones agosto 2026")

    assert "borrador" in august.response_text.lower()
    assert "Dr. Cabo Transcript" in july.response_text
    assert "Dr. Cabo Transcript" in ranking.response_text
    assert all("id" not in response.response_text.lower() for response in (august, july, ranking))
