"""
DB-backed integration tests for ToolGateway.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import UTC, datetime

from backend.app.application.telegram.tools import ToolGateway
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository

UTC = UTC


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _new_doctor(db_session, *, active: bool = True, in_service: bool = True):
    from backend.app.infrastructure.db.models.doctors import DoctorModel

    doc_name = f"Dr. Test {uuid.uuid4().hex[:6]}"
    d = DoctorModel(
        id=str(uuid.uuid4()),
        name=doc_name,
        normalized_name=" ".join(doc_name.strip().lower().split()),
        sex="M",
        active=active,
        service_active=in_service,
        availability_mode="variable",
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        rank_id=None,
        department_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(d)
    db_session.flush()
    return d


def _make_gateway(db_session) -> ToolGateway:
    return ToolGateway(
        doctor_repo=DoctorRepository(db_session),
        calendar_repo=CalendarRepository(db_session),
        mission_repo=MissionRepository(db_session),
        availability_repo=AvailabilityRepository(db_session),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_unknown_intent_returns_out_of_domain(db_session) -> None:
    """An intent not in the handler map should return out_of_domain error."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("something_unknown", {})

    assert result["ok"] is False
    assert result["error"] == "out_of_domain"


def test_count_medicos_activos_empty(db_session) -> None:
    """With no doctors seeded, count should be 0."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("count_medicos_activos", {})

    assert result["ok"] is True
    assert result["data"]["count"] == 0


def test_count_medicos_activos_with_doctors(db_session) -> None:
    """One active, in-service doctor seeded → count should be 1."""
    _new_doctor(db_session, active=True, in_service=True)

    gateway = _make_gateway(db_session)
    result = gateway.execute("count_medicos_activos", {})

    assert result["ok"] is True
    assert result["data"]["count"] == 1


def test_list_medicos_activos(db_session) -> None:
    """Two doctors seeded (1 active+in_service, 1 active+NOT in_service) → returned list has 1 entry."""
    _new_doctor(db_session, active=True, in_service=True)
    _new_doctor(db_session, active=True, in_service=False)

    gateway = _make_gateway(db_session)
    result = gateway.execute("list_medicos_activos", {})

    assert result["ok"] is True
    doctors = result["data"]["doctors"]
    assert len(doctors) == 1


def test_historial_medico_not_found(db_session) -> None:
    """Asking for a doctor that does not exist should return found=False."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("historial_medico", {"doctor_name": "Dr. Nobody"})

    assert result["ok"] is True
    assert result["data"]["found"] is False


def test_pendientes_disponibilidad_mes_all_missing(db_session) -> None:
    """An active in-service doctor with no availability records for the period → count >= 1."""
    _new_doctor(db_session, active=True, in_service=True)

    gateway = _make_gateway(db_session)
    result = gateway.execute(
        "pendientes_disponibilidad_mes",
        {"month": 5, "year": 2026},
    )

    assert result["ok"] is True
    assert result["data"]["count"] >= 1


def test_historial_medico_found_by_name(db_session) -> None:
    """Doctor encontrado por nombre → found=True, datos correctos, load_60d = 0 sin asignaciones."""
    doc = _new_doctor(db_session, active=True, in_service=True)
    gateway = _make_gateway(db_session)

    result = gateway.execute("historial_medico", {"doctor_name": doc.name[:8]})

    assert result["ok"] is True
    data = result["data"]
    assert data["found"] is True
    assert data["doctor_id"] == doc.id
    assert data["assignments_60d"] == 0
    assert data["load_60d"] == 0.0


def test_historial_medico_found_by_id(db_session) -> None:
    """Doctor encontrado por doctor_id → found=True."""
    doc = _new_doctor(db_session, active=True, in_service=True)
    gateway = _make_gateway(db_session)

    result = gateway.execute("historial_medico", {"doctor_id": doc.id})

    assert result["ok"] is True
    assert result["data"]["found"] is True
    assert result["data"]["doctor_id"] == doc.id


def test_historial_medico_load_uses_area_weights(db_session) -> None:
    """Con catalog_repo inyectado, load_60d usa los pesos reales de service_areas."""
    import uuid as _uuid
    from datetime import UTC as _UTC
    from datetime import date as _date
    from datetime import datetime as _dt

    from backend.app.infrastructure.db.models.calendars import (
        CalendarAssignmentModel,
        CalendarModel,
        CalendarVersionModel,
    )
    from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository

    # Crear doctor
    doc = _new_doctor(db_session, active=True, in_service=True)

    # Crear service area con peso = 2.0
    now = _dt.now(_UTC)
    sa = ServiceAreaModel(
        id=str(_uuid.uuid4()),
        code="emergencia_test",
        display_name="Emergencia Test",
        load_weight=2,
        active=True,
        required_for_daily_coverage=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(sa)

    # Crear cadena calendario → versión → asignación hoy (dentro de 60 días)
    cal = CalendarModel(
        id=str(_uuid.uuid4()), month=5, year=2026, status="draft",
        created_by=None, created_at=now, updated_at=now,
    )
    db_session.add(cal)
    ver = CalendarVersionModel(
        id=str(_uuid.uuid4()), calendar_id=cal.id, version_number=1, status="draft",
        created_by=None, created_at=now,
    )
    db_session.add(ver)
    assignment = CalendarAssignmentModel(
        id=str(_uuid.uuid4()),
        calendar_version_id=ver.id,
        service_date=_date.today(),
        service_area_id=sa.id,
        doctor_id=doc.id,
        assignment_source="manual",
        created_by=None,
        created_at=now,
    )
    db_session.add(assignment)
    db_session.flush()

    # Gateway CON catalog_repo
    gateway = ToolGateway(
        doctor_repo=DoctorRepository(db_session),
        calendar_repo=CalendarRepository(db_session),
        mission_repo=MissionRepository(db_session),
        availability_repo=AvailabilityRepository(db_session),
        catalog_repo=CatalogRepository(db_session),
    )

    result = gateway.execute("historial_medico", {"doctor_id": doc.id})

    assert result["ok"] is True
    data = result["data"]
    assert data["found"] is True
    assert data["assignments_60d"] == 1
    assert data["load_60d"] == 2.0  # usa el peso real del service_area (no 1.0 hardcodeado)


# ---------------------------------------------------------------------------
# _tool_estado_calendario_mes
# ---------------------------------------------------------------------------


def test_estado_calendario_mes_not_found(db_session) -> None:
    """Sin calendario para el período → found=False."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("estado_calendario_mes", {"month": 1, "year": 2020})

    assert result["ok"] is True
    assert result["data"]["found"] is False


def test_estado_calendario_mes_with_calendar(db_session) -> None:
    """Calendario existente con versión → found=True, versión correcta."""
    import uuid as _uuid
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from backend.app.infrastructure.db.models.calendars import (
        CalendarModel,
        CalendarVersionModel,
    )

    now = _dt.now(_UTC)
    cal = CalendarModel(
        id=str(_uuid.uuid4()), month=6, year=2026, status="draft",
        created_by=None, created_at=now, updated_at=now,
    )
    db_session.add(cal)
    ver = CalendarVersionModel(
        id=str(_uuid.uuid4()), calendar_id=cal.id, version_number=1, status="draft",
        created_by=None, created_at=now,
    )
    db_session.add(ver)
    db_session.flush()

    gateway = _make_gateway(db_session)
    result = gateway.execute("estado_calendario_mes", {"month": 6, "year": 2026})

    assert result["ok"] is True
    data = result["data"]
    assert data["found"] is True
    assert data["version_number"] == 1
    assert data["assignments"] == 0
    assert data["gaps"] == 0


# ---------------------------------------------------------------------------
# _tool_recommend_mission_candidates — inputs inválidos
# ---------------------------------------------------------------------------


def test_recommend_mission_candidates_missing_date(db_session) -> None:
    """Sin mission_date → found=False con reason=missing_mission_date."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("recommend_mission_candidates", {"participant_count": 2})

    assert result["ok"] is True
    assert result["data"]["found"] is False
    assert result["data"]["reason"] == "missing_mission_date"


def test_recommend_mission_candidates_invalid_date(db_session) -> None:
    """mission_date con formato inválido → found=False con reason=invalid_date_format."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("recommend_mission_candidates", {
        "mission_date": "32-13-2026",
        "participant_count": 1,
    })

    assert result["ok"] is True
    assert result["data"]["found"] is False
    assert result["data"]["reason"] == "invalid_date_format"


# ---------------------------------------------------------------------------
# _tool_create_mission — inputs inválidos
# ---------------------------------------------------------------------------


def test_create_mission_missing_fields(db_session) -> None:
    """Sin mission_date ni doctor_ids → ok=False con error descriptivo."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("create_mission", {})

    # execute() wraps handler return in {"ok": True, "data": handler_return}
    # but handler returns {"ok": False, "error": "..."} for validation failures
    assert result["ok"] is True
    assert result["data"]["ok"] is False
    assert "Faltan datos" in result["data"]["error"]


def test_create_mission_missing_actor_id(db_session) -> None:
    """Con mission_date y doctor_ids pero sin _actor_id → ok=False."""
    gateway = _make_gateway(db_session)
    result = gateway.execute("create_mission", {
        "mission_date": "2026-06-15",
        "doctor_ids": ["some-id"],
    })

    # handler returns {"ok": False, "error": "..."} wrapped by execute()
    assert result["ok"] is True
    assert result["data"]["ok"] is False


# ---------------------------------------------------------------------------
# Report tools con mock report_service
# ---------------------------------------------------------------------------


def _make_gateway_with_reports(db_session) -> ToolGateway:
    """Gateway con ReportService mockeado para tests de report tools."""

    class FakeReportService:
        def generate_calendar_excel(self, calendar_id):
            return b"FAKE_EXCEL"

        def generate_calendar_pdf(self, calendar_id):
            return b"FAKE_PDF"

        def generate_doctor_history_excel(self, year, month):
            return b"FAKE_EXCEL_HIST"

        def generate_doctor_history_pdf(self, year, month):
            return b"FAKE_PDF_HIST"

        def generate_operational_summary_pdf(self, year, month):
            return b"FAKE_PDF_OPER"

        def generate_mission_ranking_pdf(self, year, month):
            return b"FAKE_PDF_RANK"

    return ToolGateway(
        doctor_repo=DoctorRepository(db_session),
        calendar_repo=CalendarRepository(db_session),
        mission_repo=MissionRepository(db_session),
        availability_repo=AvailabilityRepository(db_session),
        report_service=FakeReportService(),
    )


def test_generate_doctor_history_report_pdf(db_session) -> None:
    """generate_doctor_history_report con format=pdf → document_bytes con PDF."""
    gateway = _make_gateway_with_reports(db_session)
    result = gateway.execute("generate_doctor_history_report", {"month": 5, "year": 2026})

    # execute() wraps handler return in {"ok": True, "data": handler_return}
    # handler_return itself is {"ok": True, "data": ..., "document_bytes": ..., "document_filename": ...}
    assert result["ok"] is True
    inner = result["data"]
    assert inner.get("document_bytes") == b"FAKE_PDF_HIST"
    assert "historial" in inner.get("document_filename", "").lower()


def test_generate_operational_summary_pdf(db_session) -> None:
    """generate_operational_summary → document_bytes con PDF."""
    gateway = _make_gateway_with_reports(db_session)
    result = gateway.execute("generate_operational_summary", {"month": 5, "year": 2026})

    assert result["ok"] is True
    inner = result["data"]
    assert inner.get("document_bytes") == b"FAKE_PDF_OPER"
