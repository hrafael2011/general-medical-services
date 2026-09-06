"""Tests del catálogo MCP del bot (2026-09-05).

Cubre el contrato del catálogo de 22 tools, la delegación a services de
application, la propiedad de solo lectura, el gate de roles del orchestrator,
la matriz de flags del router y el bloqueo de endpoints debug en producción.
"""

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event, select

from backend.app.application.telegram import tool_handlers, tool_registry
from backend.app.application.telegram.bot_client import FakeBotClient
from backend.app.application.telegram.orchestrator import TelegramOrchestrator
from backend.app.application.telegram.types import AgentResult
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel
from backend.app.infrastructure.db.models.calendars import CalendarModel, CalendarVersionModel
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.telegram import TelegramUserLinkModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository

# ---------------------------------------------------------------------------
# 1. Contrato del catálogo (test_catalog_contract)
# ---------------------------------------------------------------------------


def test_catalog_has_exactly_22_tools() -> None:
    names = [t["name"] for t in tool_registry.ALL_TOOLS]
    assert len(names) == 22
    assert len(set(names)) == 22, "Nombres de tools duplicados"


def test_catalog_has_no_sql_query() -> None:
    names = [t["name"] for t in tool_registry.ALL_TOOLS]
    assert "sql_query" not in names
    assert "sql_query" not in tool_registry.build_tools_prompt()


def test_every_tool_has_canonical_question_in_description() -> None:
    for tool in tool_registry.ALL_TOOLS:
        name = tool["name"]
        canonical = tool_registry.CANONICAL_QUESTIONS[name]
        assert canonical in tool["description"], (
            f"La descripción de {name} no contiene su pregunta canónica."
        )
        # Sin descripciones ambiguas del catálogo viejo.
        assert "sql_query" not in tool["description"]


def test_every_tool_schema_is_object_with_properties() -> None:
    for tool in tool_registry.ALL_TOOLS:
        params = tool["parameters"]
        assert params.get("type") == "object"
        assert isinstance(params.get("properties"), dict)
        # Tipos de propiedades válidos
        for pname, pschema in params["properties"].items():
            assert pschema.get("type") in ("string", "integer", "boolean", "object"), (
                f"{tool['name']}.{pname} tiene type inválido"
            )


def test_bounded_values_use_enums() -> None:
    by_name = {t["name"]: t for t in tool_registry.ALL_TOOLS}

    sex = by_name["list_doctors"]["parameters"]["properties"]["sex"]
    assert sex["enum"] == ["M", "F"]

    criterion = by_name["workload_ranking"]["parameters"]["properties"]["criterion"]
    assert criterion["enum"] == ["load", "target_gap"]

    rtype = by_name["generate_report"]["parameters"]["properties"]["type"]
    assert rtype["enum"] == ["monthly", "weekly"]

    reply = by_name["reply"]["parameters"]["properties"]["response_type"]
    assert reply["enum"] == ["greeting", "help", "farewell", "clarify", "out_of_scope"]


def test_required_params_are_declared() -> None:
    by_name = {t["name"]: t for t in tool_registry.ALL_TOOLS}
    assert "doctor_name" in by_name["doctor_info"]["parameters"]["required"]
    assert "start_date" in by_name["calendar_assignments"]["parameters"]["required"]
    assert "date" in by_name["slot_recommendation"]["parameters"]["required"]
    assert "month" in by_name["calendar_status"]["parameters"]["required"]
    assert "mission_date" in by_name["mission_candidates"]["parameters"]["required"]


# ---------------------------------------------------------------------------
# 2. Solo lectura (test_tools_are_read_only)
# ---------------------------------------------------------------------------


def _normalized(name: str) -> str:
    import unicodedata

    return (
        unicodedata.normalize("NFD", name)
        .encode("ascii", "ignore")
        .decode()
        .upper()
    )


def _seed(db_session):
    now = datetime.now(UTC)
    area = ServiceAreaModel(
        id=str(uuid.uuid4()),
        code="emergencia",
        display_name="Emergencia",
        active=True,
        required_for_daily_coverage=True,
        load_weight=3,
        created_at=now,
        updated_at=now,
    )
    db_session.add(area)
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="Dr. Catálogo",
        normalized_name=_normalized("Dr. Catálogo"),
        sex="M",
        rank_id=None,
        department_id=None,
        active=True,
        service_active=True,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        pool_active=True,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(doctor)
    calendar = CalendarModel(
        id=str(uuid.uuid4()),
        year=2026,
        month=5,
        status="draft",
        generation_mode="manual",
        created_by=None,
        approved_by=None,
        created_at=now,
        updated_at=now,
        approved_at=None,
    )
    db_session.add(calendar)
    db_session.flush()
    version = CalendarVersionModel(
        id=str(uuid.uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status="draft",
        created_by=None,
        reason=None,
        created_at=now,
    )
    db_session.add(version)
    db_session.flush()
    return area, doctor, calendar, version


def test_handlers_never_write(db_session) -> None:
    """Ningún handler del catálogo dispara flush/commit en la sesión."""
    area, doctor, calendar, version = _seed(db_session)
    now = datetime.now(UTC)
    db_session.add(DoctorAvailabilityModel(
        id=str(uuid.uuid4()),
        doctor_id=doctor.id,
        availability_type="monthly_variable",
        days_of_week=None,
        available_dates=[1, 2, 3],
        weekday=None,
        week_number=None,
        year=2026,
        month=5,
        day_priority="available",
        submitted_at=None,
        effective_from=None,
        effective_to=None,
        source="manual",
        review_status="approved",
        created_by=None,
        created_at=now,
        updated_at=now,
    ))
    db_session.flush()

    writes: list[str] = []
    event.listen(db_session, "after_flush", lambda *a: writes.append("flush"))
    event.listen(db_session, "after_commit", lambda *a: writes.append("commit"))

    handlers = tool_handlers.build_tool_handlers(session=db_session)
    assert len(handlers) == 21  # reply no tiene handler de datos

    calls = [
        ("list_doctors", {}),
        ("doctor_info", {"doctor_name": "Catálogo"}),
        ("doctor_availability", {"doctor_name": "Catálogo", "month": 5, "year": 2026}),
        ("doctor_restrictions", {"doctor_name": "Catálogo", "month": 5, "year": 2026}),
        ("doctor_service_history", {"doctor_name": "Catálogo", "month": 5, "year": 2026}),
        ("workload_ranking", {"month": 5, "year": 2026}),
        ("calendar_assignments", {"start_date": "2026-05-01", "end_date": "2026-05-31"}),
        ("calendar_status", {"month": 5, "year": 2026}),
        ("slot_recommendation", {"date": "2026-05-15", "service_area": "Emergencia"}),
        ("slot_explanation", {"date": "2026-05-15", "service_area": "Emergencia", "doctor_name": "Catálogo"}),
        ("doctors_available_on", {"date": "2026-05-15"}),
        ("availability_report_status", {"month": 5, "year": 2026}),
        ("mission_list", {}),
        ("confirmation_status", {"month": 5, "year": 2026}),
        ("notification_status", {"month": 5, "year": 2026}),
        ("action_alerts", {"status": "open"}),
        ("audit_history", {}),
        ("system_config", {}),
    ]
    for tool_name, params in calls:
        result = handlers[tool_name](**params)
        assert isinstance(result, dict), f"{tool_name} no devolvió dict"
        assert result.get("ok") is True, f"{tool_name} falló: {result}"
        assert writes == [], (
            f"{tool_name} escribió en la sesión (flush/commit)"
        )


# ---------------------------------------------------------------------------
# 3. Delegación a services de application (test_tools_delegate)
# ---------------------------------------------------------------------------


def _deps_with_mocks() -> dict:
    """Deps mínimo con mocks para verificar delegación de handlers."""
    session = MagicMock()
    session.get.return_value = None

    area = SimpleNamespace(id="area-1", display_name="Emergencia", code="emergencia")
    doctor = SimpleNamespace(id="doc-1", name="Dr. Mock")

    catalog_repo = MagicMock()
    catalog_repo.list_service_areas.return_value = [area]

    calendar_repo = MagicMock()
    calendar_repo.get_calendar_by_period.return_value = SimpleNamespace(id="cal-1")
    calendar_repo.get_latest_version.return_value = SimpleNamespace(id="ver-1")

    assignment_service = MagicMock()
    assignment_service.get_eligible_doctors_for_slot.return_value = {
        "eligible": [{"doctor": doctor, "altera_orden": None}],
        "unavailable": [],
    }

    availability_service = MagicMock()
    availability_service.get_available_doctor_ids.return_value = ["doc-1", "doc-2"]

    candidate_service = MagicMock()
    candidate_service.recommend_candidates.return_value = {
        "candidates": [{"doctor_id": "doc-1", "score": 0.9}]
    }

    doctor_repo = MagicMock()
    doctor_repo.list_service_active.return_value = [doctor]
    doctor_repo.get_allowed_areas.return_value = ["area-1"]

    return {
        "session": session,
        "doctor_repo": doctor_repo,
        "calendar_repo": calendar_repo,
        "catalog_repo": catalog_repo,
        "mission_repo": MagicMock(),
        "availability_repo": MagicMock(),
        "alert_repo": MagicMock(),
        "audit_repo": MagicMock(),
        "confirmation_repo": MagicMock(),
        "availability_service": availability_service,
        "assignment_service": assignment_service,
        "candidate_service": candidate_service,
        "report_service": MagicMock(),
        "doctor_names": {"doc-1": "Dr. Mock", "doc-2": "Dr. Dos"},
        "user_names": {},
        "rank_ids": {},
        "department_ids": {},
    }


def test_slot_recommendation_delegates_to_assignment_service() -> None:
    deps = _deps_with_mocks()
    result = tool_handlers.handle_slot_recommendation(
        {"date": "2026-05-15", "service_area": "Emergencia"}, deps
    )
    assert result["ok"] is True
    deps["assignment_service"].get_eligible_doctors_for_slot.assert_called_once()
    assert result["rows"][0]["name"] == "Dr. Mock"


def test_doctors_available_on_delegates_to_availability_service() -> None:
    deps = _deps_with_mocks()
    result = tool_handlers.handle_doctors_available_on({"date": "2026-05-15"}, deps)
    deps["availability_service"].get_available_doctor_ids.assert_called_once()
    assert result["ok"] is True


def test_mission_candidates_delegates_to_candidate_service() -> None:
    deps = _deps_with_mocks()
    result = tool_handlers.handle_mission_candidates(
        {"mission_date": "2026-05-20", "count": 3}, deps
    )
    deps["candidate_service"].recommend_candidates.assert_called_once()
    assert result["ok"] is True


def test_calendar_status_uses_calendar_repository() -> None:
    deps = _deps_with_mocks()
    deps["calendar_repo"].get_calendar_by_period.return_value = SimpleNamespace(
        id="cal-1", status="draft"
    )
    deps["calendar_repo"].get_latest_version.return_value = SimpleNamespace(id="ver-1")
    deps["calendar_repo"].list_assignments.return_value = []
    deps["calendar_repo"].list_weeks.return_value = []
    session = deps["session"]
    session.scalars.return_value = []
    result = tool_handlers.handle_calendar_status({"month": 5, "year": 2026}, deps)
    deps["calendar_repo"].get_calendar_by_period.assert_called_once_with(2026, 5)
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# 4. Gate de roles (test_doctor_role_denied_for_queries)
# ---------------------------------------------------------------------------


def _new_user(db_session, *, role: str) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Test User",
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    return user


def _new_link(db_session, *, user_id: str) -> TelegramUserLinkModel:
    link = TelegramUserLinkModel(
        id=str(uuid.uuid4()),
        telegram_user_id=str(uuid.uuid4()),
        telegram_username="testuser",
        user_id=user_id,
        active=True,
        linked_by=None,
        linked_at=datetime.now(UTC),
        last_used_at=None,
    )
    db_session.add(link)
    db_session.flush()
    return link


class StubAgent:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def process(self, *args, **kwargs) -> AgentResult:
        self.calls.append(kwargs.get("text", ""))
        return AgentResult(response_text="Respuesta del agente")


def _make_orchestrator(db_session, *, agent=None) -> TelegramOrchestrator:
    return TelegramOrchestrator(
        telegram_repo=TelegramRepository(db_session),
        user_repo=UserRepository(db_session),
        agent=agent or StubAgent(),
        bot_client=FakeBotClient(),
    )


def test_doctor_role_denied_for_queries(db_session) -> None:
    user = _new_user(db_session, role="doctor")
    link = _new_link(db_session, user_id=user.id)
    agent = StubAgent()
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=link.telegram_user_id,
        telegram_username="testuser",
        chat_id=123,
        text="¿Quiénes están de guardia mañana?",
    )

    assert "solo para el encargado" in response
    assert agent.calls == [], "El agente no debe ejecutarse para rol doctor"


def test_encargado_role_allowed_for_queries(db_session) -> None:
    user = _new_user(db_session, role="encargado")
    link = _new_link(db_session, user_id=user.id)
    agent = StubAgent()
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=link.telegram_user_id,
        telegram_username="testuser",
        chat_id=123,
        text="¿Quiénes están de guardia mañana?",
    )

    assert agent.calls, "El agente debe ejecutarse para encargado"
    assert response == "Respuesta del agente"


# ---------------------------------------------------------------------------
# 5. Matriz de flags del router (test_router_flags_matrix)
# ---------------------------------------------------------------------------


def test_router_flag_on_handles_chitchat_without_agent(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_telegram_router", True)
    monkeypatch.setattr(settings, "feature_telegram_router_chitchat", True)
    user = _new_user(db_session, role="encargado")
    link = _new_link(db_session, user_id=user.id)
    agent = StubAgent()
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=link.telegram_user_id,
        telegram_username="testuser",
        chat_id=123,
        text="hola",
    )

    assert agent.calls == [], "Chitchat no debe llegar al agente"
    assert "Hola" in response


def test_router_flag_off_falls_back_to_agent(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_telegram_router", False)
    user = _new_user(db_session, role="encargado")
    link = _new_link(db_session, user_id=user.id)
    agent = StubAgent()
    orchestrator = _make_orchestrator(db_session, agent=agent)

    response = orchestrator.handle_message(
        telegram_user_id=link.telegram_user_id,
        telegram_username="testuser",
        chat_id=123,
        text="hola",
    )

    assert agent.calls, "Con el flag apagado el mensaje cae al agente"
    assert response == "Respuesta del agente"


# ---------------------------------------------------------------------------
# 6. Endpoints debug bloqueados en producción
# ---------------------------------------------------------------------------


def test_debug_endpoints_blocked_in_production(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    monkeypatch.setattr(settings, "app_env", "production")
    app = create_app()
    client = TestClient(app)

    resp_diag = client.get("/api/webhooks/diagnostic?secret=whatever")
    assert resp_diag.status_code == 404

    resp_notify = client.post("/api/webhooks/test-notify?secret=whatever")
    assert resp_notify.status_code == 404


def test_debug_endpoints_available_outside_production(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "webhook_test_secret", "")
    app = create_app()
    client = TestClient(app)

    # Sin secret configurado → 500 (el guard de producción no aplica).
    resp_diag = client.get("/api/webhooks/diagnostic?secret=whatever")
    assert resp_diag.status_code == 500
