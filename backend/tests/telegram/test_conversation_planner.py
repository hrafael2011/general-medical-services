from backend.app.application.telegram.conversation_planner import (
    ConversationPlan,
    build_conversation_plan,
)
from backend.app.application.telegram.memory import SessionState


def test_planner_returns_structured_plan_for_doctor_availability_count():
    plan = build_conversation_plan("cuantos medicos tengo disponible")

    assert isinstance(plan, ConversationPlan)
    assert plan.domain == "medicos"
    assert plan.action == "contar"
    assert plan.route == "deterministic_service"
    assert plan.memory_policy == "none"
    assert plan.is_followup is False


def test_planner_treats_active_for_service_as_doctor_status_not_calendar():
    plan = build_conversation_plan("dame la lista de medicos inactivos para servicio")

    assert plan.domain == "medicos"
    assert plan.action == "listar"


def test_planner_routes_calendar_week_questions_to_calendar_domain():
    plan = build_conversation_plan(
        "cuales medicos estan de servicio en la primera semana de julio 2026"
    )

    assert plan.domain == "calendario"
    assert plan.action == "listar"
    assert plan.route == "deterministic_service"
    assert plan.is_followup is False


def test_planner_prioritizes_mission_ranking_over_calendar_followup():
    previous = SessionState(
        last_domain="calendar_assignments",
        last_query_type="count_assigned_doctors_by_month",
        last_period={"year": 2026, "month": 7},
    )

    plan = build_conversation_plan(
        "cuales son los 3 medicos que tengo en el ranking de misiones agosto 2026",
        session_state=previous,
    )

    assert plan.domain == "ranking_misiones"
    assert plan.action == "listar"
    assert plan.route == "registry_query"
    assert plan.is_followup is False
    assert plan.memory_policy == "none"


def test_planner_allows_short_month_followup_for_calendar_context():
    previous = SessionState(
        last_domain="calendar_assignments",
        last_query_type="count_assigned_doctors_by_month",
        last_period={"year": 2026, "month": 8},
    )

    plan = build_conversation_plan("y el de julio?", session_state=previous)

    assert plan.domain == "calendario"
    assert plan.action == "contar"
    assert plan.is_followup is True
    assert plan.memory_policy == "reuse_last_period"


def test_planner_routes_confirmation_questions_before_doctors():
    plan = build_conversation_plan("que medicos no han confirmado servicio en julio 2026")

    assert plan.domain == "confirmaciones"
    assert plan.action == "listar"
    assert plan.route == "registry_query"


def test_planner_asks_clarification_for_low_confidence_data_request():
    plan = build_conversation_plan("dame eso")

    assert plan.route == "clarification"
    assert plan.confidence < 0.6
    assert plan.clarification_question is not None
