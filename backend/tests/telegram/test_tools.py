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
