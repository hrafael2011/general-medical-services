import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.calendar_query_service import CalendarQueryService
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.application.telegram.memory import SessionStore
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel


def _seed_area(session) -> ServiceAreaModel:
    existing = session.scalars(
        select(ServiceAreaModel).where(ServiceAreaModel.code == "EMERG")
    ).first()
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    area = ServiceAreaModel(
        id=str(uuid.uuid4()),
        code="EMERG",
        display_name="Emergencia",
        load_weight=1,
        active=True,
        required_for_daily_coverage=True,
        created_at=now,
        updated_at=now,
    )
    session.add(area)
    session.flush()
    return area


def _seed_doctor(session, name: str) -> DoctorModel:
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name=name,
        normalized_name=name.lower(),
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
    session.add(doctor)
    session.flush()
    return doctor


def _seed_calendar_assignment(session, *, year: int, month: int, status: str, service_date: date, doctor_name: str):
    now = datetime.now(UTC)
    area = _seed_area(session)
    doctor = _seed_doctor(session, doctor_name)
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
            service_date=service_date,
            service_area_id=area.id,
            doctor_id=doctor.id,
            assignment_source="manual",
            created_at=now,
        )
    )
    session.commit()


def _agent(session) -> tuple[ConversationalAgent, FakeLLMProvider]:
    llm = FakeLLMProvider(responses={
        "julio": '{"action": "reply", "response_text": "No se encontraron resultados."}',
        "agosto": '{"action": "reply", "response_text": "No se encontraron resultados."}',
    })
    router = IntentRouter()
    router.set_session(session)
    return (
        ConversationalAgent(
            llm=llm,
            router=router,
            calendar_query_service=CalendarQueryService(session),
        ),
        llm,
    )


def test_first_week_query_uses_approved_calendar_assignments(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 3),
        doctor_name="Dr. Julio Aprobado",
    )
    agent, llm = _agent(db_session)

    result = agent.process("cuales son los medicos de servicio la primera semana de julio 2026")

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "Dr. Julio Aprobado" in result.response_text
    assert result.tool_entities["period"] == {
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
    }
    assert llm.calls == []


def test_first_week_query_mentions_draft_when_no_approved_calendar(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        service_date=date(2026, 8, 4),
        doctor_name="Dr. Agosto Borrador",
    )
    agent, llm = _agent(db_session)

    result = agent.process("cuales son los medicos de servicio la primera semana de agosto 2026")

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "no hay calendario aprobado" in result.response_text.lower()
    assert "borrador" in result.response_text.lower()
    assert result.tool_result["draft_count"] == 1
    assert llm.calls == []


def test_first_week_month_followup_reuses_previous_week_range(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        service_date=date(2026, 8, 4),
        doctor_name="Dr. Agosto Borrador",
    )
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 4),
        doctor_name="Dr. Julio Seguimiento",
    )
    llm = FakeLLMProvider(responses={
        "julio": '{"action": "reply", "response_text": "No se encontraron resultados."}',
        "agosto": '{"action": "reply", "response_text": "No se encontraron resultados."}',
    })
    router = IntentRouter()
    router.set_session(db_session)
    agent = ConversationalAgent(
        llm=llm,
        router=router,
        calendar_query_service=CalendarQueryService(db_session),
        session_store=SessionStore(),
    )

    first = agent.process(
        "cuales son los medicos que estan de servicio la primera semana de agosto 2026",
        telegram_user_id="tg-calendar-transcript",
    )
    followup = agent.process(
        "ok entiendo y de julio ?",
        telegram_user_id="tg-calendar-transcript",
    )

    assert "borrador" in first.response_text.lower()
    assert followup.agent_action == "query"
    assert followup.tool_name == "calendar_query_service"
    assert "Dr. Julio Seguimiento" in followup.response_text
    assert followup.tool_entities["period"] == {
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
    }
    assert llm.calls == []


def test_monthly_assigned_doctor_count_uses_approved_calendar(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 10),
        doctor_name="Dr. Julio Mensual",
    )
    agent, llm = _agent(db_session)

    result = agent.process("cuantos medicos estan incluidos en el calendario de julio 2026")

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert result.tool_result["data"]["rows"] == [{"total": 1}]
    assert result.tool_result["status_used"] == "approved"
    assert "total: 1" in result.response_text
    assert llm.calls == []


def test_monthly_assigned_doctor_count_mentions_draft_when_no_approved_calendar(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        service_date=date(2026, 8, 10),
        doctor_name="Dr. Agosto Mensual",
    )
    agent, llm = _agent(db_session)

    result = agent.process("cuantos medicos estan incluidos en el calendario de agosto 2026")

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "no hay calendario aprobado" in result.response_text.lower()
    assert "borrador" in result.response_text.lower()
    assert result.tool_result["draft_count"] == 1
    assert llm.calls == []
