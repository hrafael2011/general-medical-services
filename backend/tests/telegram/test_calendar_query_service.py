"""Tests del CalendarQueryService — contrato post-tools (2026-09-06).

El bot migró a function calling con catálogo MCP (spec 15). El service interno
`CalendarQueryService` sigue vivo como backend determinista de las tools
`calendar_assignments`, `calendar_assigned_count` y `calendar_status`
(dispatch en `ConversationalAgent._dispatch_tool` y `_process_legacy`;
cableado en `api/routes/telegram.py`). Estos tests lo ejercitan por su API
real: `execute(query_type, params)`.

El clasificador legacy que parseaba frases como «la primera semana de julio»
(typos, orden invertido, reutilización del rango en follow-ups, export
contextual del listado anterior) fue removido del producto: esas capacidades
son hoy del NLU (LLM) y del catálogo de tools. Los casos que cubrían esos
paths de clasificación se eliminaron:

- «primea/seguna semana», «semana primera», sin palabra «servicio» → el
  entendimiento tolerante a variantes es del NLU, no de código determinista
  (catálogo: test_mcp_catalog.py::test_every_tool_has_canonical_question_in_description).
- follow-up que reutilizaba el rango de la semana previa («y de julio?») →
  removido: `_merge_followup_context` solo fusiona filtros rank/sex/department;
  la persistencia de sesión la cubre test_session_persistence.py.
- export contextual del listado («esporta ese listado a pdf») → la maquinaria
  de export vive en IntentRouter (test_intent_router.py::test_router_export_action_without_format,
  test_router_export_with_format_pdf) y el reporte del catálogo es
  `generate_report` (test_mcp_catalog.py::test_bounded_values_use_enums).
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from backend.app.application.telegram.calendar_query_service import CalendarQueryService
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
        sex="M",
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
    session.add(doctor)
    session.flush()
    return doctor


def _seed_calendar_assignment(
    session,
    *,
    year: int,
    month: int,
    status: str,
    service_date: date,
    doctor_name: str,
):
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


# ---------------------------------------------------------------------------
# list_calendar_assignments_by_date_range / calendar_assignments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query_type",
    ["calendar_assignments", "list_calendar_assignments_by_date_range"],
)
def test_list_assignments_approved_period_returns_doctors(db_session, query_type):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 3),
        doctor_name="Dr. Julio Aprobado",
    )
    service = CalendarQueryService(db_session)

    result = service.execute(
        query_type, {"start_date": "2026-07-01", "end_date": "2026-07-07"}
    )

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "Dr. Julio Aprobado" in result.response_text
    assert result.tool_entities["period"] == {
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
    }
    assert result.tool_result["status_used"] == "approved"
    assert result.tool_result["calendar_exists"] is True
    assert result.tool_result["draft_count"] == 0
    assert len(result.tool_result["data"]["rows"]) == 1


def test_list_assignments_draft_period_mentions_borrador(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        service_date=date(2026, 8, 4),
        doctor_name="Dr. Agosto Borrador",
    )
    service = CalendarQueryService(db_session)

    result = service.execute(
        "calendar_assignments", {"start_date": "2026-08-01", "end_date": "2026-08-07"}
    )

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "no hay calendario aprobado" in result.response_text.lower()
    assert "borrador" in result.response_text.lower()
    assert result.tool_result["calendar_exists"] is True
    assert result.tool_result["draft_count"] == 1
    assert result.tool_result["data"]["rows"] == []


def test_list_assignments_empty_period_returns_no_results(db_session):
    service = CalendarQueryService(db_session)

    result = service.execute(
        "calendar_assignments", {"start_date": "2026-07-01", "end_date": "2026-07-07"}
    )

    assert result.agent_action == "query"
    assert "No se encontraron servicios aprobados" in result.response_text
    assert result.tool_result["calendar_exists"] is False
    assert result.tool_result["draft_count"] == 0
    assert result.tool_result["data"]["rows"] == []


# ---------------------------------------------------------------------------
# count_assigned_doctors_by_month / calendar_assigned_count
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query_type",
    ["calendar_assigned_count", "count_assigned_doctors_by_month"],
)
def test_count_assigned_doctors_uses_approved_calendar(db_session, query_type):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 10),
        doctor_name="Dr. Julio Mensual",
    )
    service = CalendarQueryService(db_session)

    result = service.execute(query_type, {"year": 2026, "month": 7})

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert result.tool_entities["period"] == {"year": 2026, "month": 7}
    assert result.tool_result["data"]["rows"] == [{"total": 1}]
    assert result.tool_result["status_used"] == "approved"
    assert result.tool_result["draft_count"] == 0
    assert "total: 1" in result.response_text


def test_count_assigned_doctors_mentions_borrador_when_no_approved_calendar(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=8,
        status="draft",
        service_date=date(2026, 8, 10),
        doctor_name="Dr. Agosto Mensual",
    )
    service = CalendarQueryService(db_session)

    result = service.execute("calendar_assigned_count", {"year": 2026, "month": 8})

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert "no hay calendario aprobado" in result.response_text.lower()
    assert "borrador" in result.response_text.lower()
    assert result.tool_result["calendar_exists"] is True
    assert result.tool_result["draft_count"] == 1
    assert result.tool_result["data"]["rows"] == [{"total": 0}]


# ---------------------------------------------------------------------------
# calendar_status
# ---------------------------------------------------------------------------


def test_calendar_status_existing_calendar(db_session):
    _seed_calendar_assignment(
        db_session,
        year=2026,
        month=7,
        status="approved",
        service_date=date(2026, 7, 10),
        doctor_name="Dr. Julio Estado",
    )
    service = CalendarQueryService(db_session)

    result = service.execute("calendar_status", {"year": 2026, "month": 7})

    assert result.agent_action == "query"
    assert result.tool_name == "calendar_query_service"
    assert result.tool_entities["period"] == {"year": 2026, "month": 7}
    assert result.tool_result["calendar_exists"] is True
    assert "approved" in result.response_text


def test_calendar_status_missing_calendar(db_session):
    service = CalendarQueryService(db_session)

    result = service.execute("calendar_status", {"year": 2026, "month": 9})

    assert result.agent_action == "query"
    assert result.tool_result["calendar_exists"] is False
    assert "No existe un calendario" in result.response_text


# ---------------------------------------------------------------------------
# Contrato del execute()
# ---------------------------------------------------------------------------


def test_unknown_query_type_returns_none(db_session):
    """Fuera de los 5 query types soportados, execute() devuelve None."""
    service = CalendarQueryService(db_session)

    assert service.execute("assign_by_week", {}) is None
