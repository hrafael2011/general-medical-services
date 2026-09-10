"""Tests for the system context builder.

Corren contra el schema real de PostgreSQL (fixture global `db_session`) y
siembran con los modelos ORM de producción — nada de DDL ad-hoc.
"""

import logging
from datetime import UTC, date, datetime
from uuid import uuid4

from backend.app.application.telegram.system_context import build_system_context
from backend.app.infrastructure.db.models.calendars import (
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import MissionAssignmentModel


def _seed_catalogs(db_session) -> None:
    """Siembra el mismo juego de datos de la versión SQLite del test, pero con
    los modelos reales (columnas y constraints de producción)."""
    now = datetime.now(UTC)

    calendar = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="approved",
        created_at=now, updated_at=now,
    )

    db_session.add_all([
        RankModel(id=str(uuid4()), name="Cabo", normalized_name="Cabo",
                  abbreviation="CB", active=True, created_at=now, updated_at=now),
        RankModel(id=str(uuid4()), name="Sargento", normalized_name="Sargento",
                  abbreviation="SG", active=True, created_at=now, updated_at=now),
        RankModel(id=str(uuid4()), name="Mayor", normalized_name="Mayor",
                  abbreviation="MY", active=True, created_at=now, updated_at=now),
        DepartmentModel(id=str(uuid4()), name="Medicina General",
                        normalized_name="medicina general", active=True,
                        created_at=now, updated_at=now),
        ServiceAreaModel(id=str(uuid4()), code="emergencia",
                         display_name="Emergencia", load_weight=1,
                         created_at=now, updated_at=now),
        DoctorModel(id=str(uuid4()), name="Doctor Uno",
                    normalized_name="doctor uno", sex="M",
                    availability_mode="available", whatsapp_phone="0000000001",
                    created_at=now, updated_at=now),
        DoctorModel(id=str(uuid4()), name="Doctor Dos",
                    normalized_name="doctor dos", sex="F",
                    availability_mode="available", whatsapp_phone="0000000002",
                    created_at=now, updated_at=now),
        calendar,
        CalendarVersionModel(id=str(uuid4()), calendar_id=calendar.id,
                             version_number=1, status="approved",
                             created_at=now),
        MissionAssignmentModel(id=str(uuid4()), mission_date=date(2026, 5, 10),
                               participant_count=2, status="active",
                               created_at=now, updated_at=now),
        DeactivationReasonModel(id=str(uuid4()), code="licencia_medica",
                                display_name="Licencia médica", severity="media",
                                created_at=now, updated_at=now),
    ])
    # La fixture arma la sesión con autoflush=False: materializar los INSERT
    # antes de las consultas con SQL crudo de build_system_context.
    db_session.flush()


def test_returns_string_with_valid_session(db_session):
    """Siembra catálogos reales y verifica que el contexto los refleja."""
    _seed_catalogs(db_session)

    result = build_system_context(db_session)

    assert isinstance(result, str)
    assert len(result) > 100
    assert "RANGOS MILITARES" in result
    assert "Cabo" in result
    assert "Sargento" in result
    assert "DEPARTAMENTOS" in result
    assert "Medicina General" in result
    assert "ÁREAS DE SERVICIO" in result
    assert "Emergencia" in result
    assert "SEXO" in result
    assert "M" in result
    assert "F" in result
    assert "ESTADOS DE CALENDARIO" in result
    assert "approved" in result
    assert "ESTADOS DE MISIONES" in result
    assert "active" in result
    assert "RAZONES DE BAJA" in result
    assert "Licencia médica" in result
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result


def test_handles_empty_database(db_session):
    """Sin filas, deben devolverse igual las secciones fijas."""
    result = build_system_context(db_session)

    assert isinstance(result, str)
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result


def test_handles_missing_tables_gracefully(db_session):
    """No revienta y devuelve las secciones fijas, incluso si consultas fallan.

    Con el schema real compartido ya no puede haber "tablas faltantes" (el
    conftest las crea todas al inicio de la corrida), así que se preserva la
    intención original — build_system_context nunca lanza excepción y devuelve
    las secciones fijas — contra la base vacía.
    """
    result = build_system_context(db_session)

    assert isinstance(result, str)
    assert "RANGOS MILITARES" in result
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result


def test_no_query_of_the_context_fails(db_session, caplog) -> None:
    """Ninguna consulta del contexto puede fallar.

    `_fetch` traga el error y devuelve [], así que el fallo no se ve en el
    resultado: sólo desaparece la sección, en silencio. Y en PostgreSQL es peor
    que perder una sección — una sentencia que falla aborta la transacción
    ENTERA y todo lo que venga después falla con InFailedSqlTransaction. Una
    sola consulta mal escrita se lleva puestas a las demás: pasaron 17 seguidas
    y el contexto perdió casi todas sus secciones dinámicas.

    Este test no enumera las secciones: mira si alguna consulta falló. Así
    atrapa también las que se rompan en el futuro.
    """
    _seed_catalogs(db_session)

    with caplog.at_level(
        logging.WARNING, logger="backend.app.application.telegram.system_context"
    ):
        build_system_context(db_session)

    fallos = [
        str(r.getMessage())
        for r in caplog.records
        if "System context query failed" in str(r.getMessage())
    ]
    assert fallos == [], "consultas del contexto que fallan:\n" + "\n".join(fallos)
