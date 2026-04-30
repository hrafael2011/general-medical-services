"""
DB-backed integration tests for ToolGateway.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid
from datetime import datetime, timezone

from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.application.telegram.tools import ToolGateway

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _new_doctor(db_session, *, active: bool = True, in_service: bool = True):
    from backend.app.infrastructure.db.models.doctors import DoctorModel

    d = DoctorModel(
        id=str(uuid.uuid4()),
        name=f"Dr. Test {uuid.uuid4().hex[:6]}",
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
