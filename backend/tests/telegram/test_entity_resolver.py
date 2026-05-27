"""Tests for EntityResolver — date, doctor, area, rank resolution."""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from backend.app.application.telegram.entity_resolver import EntityResolver


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------


def test_resolve_relative_date_tomorrow() -> None:
    """'mañana' se resuelve a la fecha de mañana."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("mañana")
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert result is not None
    assert result["type"] == "single_date"
    assert result["value"] == tomorrow


def test_resolve_relative_date_today() -> None:
    """'hoy' se resuelve a la fecha de hoy."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("hoy")
    today = date.today().strftime("%Y-%m-%d")
    assert result is not None
    assert result["type"] == "single_date"
    assert result["value"] == today


def test_resolve_relative_date_next_week() -> None:
    """'la próxima semana' → rango de fechas de la semana siguiente."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("la próxima semana")
    assert result is not None
    assert result["type"] == "date_range"
    assert "start" in result
    assert "end" in result


def test_resolve_relative_date_last_month() -> None:
    """'el mes pasado' → rango del mes anterior."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("el mes pasado")
    assert result is not None
    assert result["type"] == "date_range"
    assert "start" in result
    assert "end" in result


def test_resolve_relative_date_this_week() -> None:
    """'esta semana' → rango de lunes a domingo de la semana actual."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("esta semana")
    assert result is not None
    assert result["type"] == "date_range"
    assert "start" in result
    assert "end" in result


def test_resolve_relative_date_abril() -> None:
    """'abril' → type=month, month=4."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("abril")
    assert result is not None
    assert result["type"] == "month"
    assert result["month"] == 4


def test_resolve_date_not_found_returns_none() -> None:
    """Texto sin fecha retorna None."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_date_expression("no hay fecha aquí")
    assert result is None


# ---------------------------------------------------------------------------
# Doctor resolution
# ---------------------------------------------------------------------------


def test_resolve_doctor_by_name_partial_match(db_session: Session) -> None:
    """'Pérez' → resolved con 1 match."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    doc = DoctorModel(
        id=str(_uuid.uuid4()),
        name="Juan Pérez",
        normalized_name="juan perez",
        sex="male",
        active=True,
        service_active=True,
        availability_mode="variable",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=_dt.now(UTC),
        updated_at=_dt.now(UTC),
    )
    db_session.add(doc)
    db_session.flush()

    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_doctor("Pérez")

    assert result.status == "resolved"
    assert len(result.matches) == 1
    assert result.matches[0]["name"] == "Juan Pérez"


def test_resolve_doctor_exact_unique_match(db_session: Session) -> None:
    """Nombre exacto → resolved con 1 match."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    doc = DoctorModel(
        id=str(_uuid.uuid4()),
        name="María Gómez",
        normalized_name="maria gomez",
        sex="female",
        active=True,
        service_active=True,
        availability_mode="fija",
        participa_misiones=True,
        whatsapp_phone="0000000000",
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        created_at=_dt.now(UTC),
        updated_at=_dt.now(UTC),
    )
    db_session.add(doc)
    db_session.flush()

    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_doctor("María Gómez")

    assert result.status == "resolved"
    assert len(result.matches) == 1


def test_resolve_doctor_multiple_matches_is_ambiguous(db_session: Session) -> None:
    """Dos doctores con mismo apellido → ambiguous con 2 matches."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    for name in ("Juan Pérez", "Ana Pérez"):
        db_session.add(DoctorModel(
            id=str(_uuid.uuid4()),
            name=name,
            normalized_name=name.lower(),
            sex="male" if "Juan" in name else "female",
            active=True,
            service_active=True,
            availability_mode="variable",
            participa_misiones=True,
            whatsapp_phone="0000000000",
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            created_at=_dt.now(UTC),
            updated_at=_dt.now(UTC),
        ))
    db_session.flush()

    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_doctor("Pérez")

    assert result.status == "ambiguous"
    assert len(result.matches) == 2


def test_resolve_doctor_not_found(db_session: Session) -> None:
    """Nombre que no existe → not_found, matches vacío."""
    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_doctor("ZZZNotFound")
    assert result.status == "not_found"
    assert result.matches == []


# ---------------------------------------------------------------------------
# Area resolution
# ---------------------------------------------------------------------------


def test_resolve_area_by_name(db_session: Session) -> None:
    """'Emergencia' → resolved con display_name coincidente."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC
    from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel

    area = ServiceAreaModel(
        id=str(_uuid.uuid4()),
        code="EMERG",
        display_name="Emergencia",
        load_weight=2,
        created_at=_dt.now(UTC),
        updated_at=_dt.now(UTC),
    )
    db_session.add(area)
    db_session.flush()

    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_area("emergencia")

    assert result.status == "resolved"
    assert len(result.matches) == 1
    assert result.matches[0]["display_name"] == "Emergencia"


# ---------------------------------------------------------------------------
# Rank resolution
# ---------------------------------------------------------------------------


def test_resolve_rank_by_name(db_session: Session) -> None:
    """'sargento' → resolved con normalized_name coincidente."""
    import uuid as _uuid
    from datetime import datetime as _dt, UTC
    from backend.app.infrastructure.db.models.catalogs import RankModel

    rank = RankModel(
        id=str(_uuid.uuid4()),
        name="Sargento",
        normalized_name="sargento",
        abbreviation="SGT",
        created_at=_dt.now(UTC),
        updated_at=_dt.now(UTC),
    )
    db_session.add(rank)
    db_session.flush()

    resolver = EntityResolver(session=db_session)
    result = resolver.resolve_rank("sargento")

    assert result.status == "resolved"
    assert len(result.matches) == 1
    assert result.matches[0]["normalized_name"] == "sargento"


# ---------------------------------------------------------------------------
# Reference resolution for follow-ups
# ---------------------------------------------------------------------------


def test_resolve_reference_segundo() -> None:
    """'el segundo' → índice 1."""
    resolver = EntityResolver(session=None)
    state = {"last_results": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
    result = resolver.resolve_reference("el segundo", state)
    assert result == 1


def test_resolve_reference_primero() -> None:
    """'el primero' → índice 0."""
    resolver = EntityResolver(session=None)
    state = {"last_results": [{"name": "A"}, {"name": "B"}]}
    result = resolver.resolve_reference("el primero", state)
    assert result == 0


def test_resolve_reference_ultimo() -> None:
    """'el último' → índice -1 (último elemento)."""
    resolver = EntityResolver(session=None)
    state = {"last_results": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
    result = resolver.resolve_reference("el último", state)
    assert result == 2


def test_resolve_reference_no_session_state() -> None:
    """Sin session state → None."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_reference("el segundo", None)
    assert result is None


def test_resolve_reference_no_results() -> None:
    """Session state sin last_results → None."""
    resolver = EntityResolver(session=None)
    result = resolver.resolve_reference("el segundo", {})
    assert result is None


def test_resolve_reference_not_a_reference() -> None:
    """Texto que no es referencia → None."""
    resolver = EntityResolver(session=None)
    state = {"last_results": [{"name": "A"}]}
    result = resolver.resolve_reference("muéstrame los datos", state)
    assert result is None


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------


def test_pre_process_returns_resolved_ambiguous_hints_structure() -> None:
    """pre_process() retorna dict con resolved, ambiguous, hints."""
    resolver = EntityResolver(session=None)
    result = resolver.pre_process("busca a Pérez en emergencia mañana")

    assert "resolved" in result
    assert "ambiguous" in result
    assert "hints" in result
    assert isinstance(result["resolved"], dict)
    assert isinstance(result["ambiguous"], list)
    assert isinstance(result["hints"], str)
