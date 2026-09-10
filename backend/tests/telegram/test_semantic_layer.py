"""Tests for the Semantic Layer deterministic query engine."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session


from backend.app.application.telegram.semantic_layer import (
    DIMENSIONS,
    METRICS,
    SemanticLayerEngine,
    SemanticLayerResolver,
    SemanticQuery,
    Filter,
    find_dimension_by_name,
    find_metric_by_name,
    get_full_catalogue,
)
from backend.app.application.telegram.semantic_layer.engine import (
    UnsupportedDimensionError,
    UnsupportedFilterError,
    UnsupportedMetricError,
)
from datetime import UTC, date, datetime

from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import RankModel, ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel


# ---------------------------------------------------------------------------
# Model / definition tests
# ---------------------------------------------------------------------------


class TestDefinitions:
    """Ensure metrics and dimensions are properly declared."""

    def test_all_dimensions_have_unique_names(self) -> None:
        names = [d.name for d in DIMENSIONS.values()]
        assert len(names) == len(set(names))

    def test_all_metrics_have_unique_names(self) -> None:
        names = [m.name for m in METRICS.values()]
        assert len(names) == len(set(names))

    def test_metric_supported_dimensions_are_real(self) -> None:
        for metric in METRICS.values():
            for dim_name in metric.supported_dimensions:
                assert dim_name in DIMENSIONS, (
                    f"Metric '{metric.name}' references unknown dimension '{dim_name}'"
                )

    def test_metric_supported_filters_are_real(self) -> None:
        for metric in METRICS.values():
            for filter_name in metric.supported_filters:
                # filters map to dimension names in our current implementation
                assert filter_name in DIMENSIONS or filter_name in {
                    "confirmation_type", "top_n", "date"
                }, (
                    f"Metric '{metric.name}' references unknown filter '{filter_name}'"
                )

    def test_find_metric_by_name(self) -> None:
        assert find_metric_by_name("total_doctors") is not None
        assert find_metric_by_name("nonexistent") is None

    def test_find_dimension_by_name(self) -> None:
        assert find_dimension_by_name("doctor") is not None
        assert find_dimension_by_name("nonexistent") is None

    def test_catalogue_is_non_empty(self) -> None:
        cat = get_full_catalogue()
        assert "total_doctors" in cat
        assert "doctor" in cat


# ---------------------------------------------------------------------------
# Engine unit tests (no DB required)
# ---------------------------------------------------------------------------


class TestEngineValidation:
    """Engine rejects invalid queries before touching the DB."""

    def test_unknown_metric_raises(self, db_session: Session) -> None:
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(metric="does_not_exist")
        with pytest.raises(UnsupportedMetricError):
            engine.execute(sq)

    def test_unsupported_dimension_raises(self, db_session: Session) -> None:
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(
            metric="total_doctors",
            dimensions=["mission_date"],  # not supported by total_doctors
        )
        with pytest.raises(UnsupportedDimensionError):
            engine.execute(sq)

    def test_unsupported_filter_raises(self, db_session: Session) -> None:
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(
            metric="total_doctors",
            filters=[Filter(field="confirmation_type", operator="eq", value="mission")],
        )
        with pytest.raises(UnsupportedFilterError):
            engine.execute(sq)

    def test_empty_query_runs(self, db_session: Session) -> None:
        """A query with no dimensions/filters should generate valid SQL."""
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(metric="total_doctors")
        result = engine.execute(sq)
        assert result.metric_name == "total_doctors"
        assert "SELECT" in result.sql.upper()
        assert result.params == {}

    def test_list_metrics_returns_all(self, db_session: Session) -> None:
        engine = SemanticLayerEngine(db_session)
        metrics = engine.list_metrics()
        names = {m["name"] for m in metrics}
        assert "total_doctors" in names
        assert "mission_ranking" in names
        assert len(metrics) == len(METRICS)


# ---------------------------------------------------------------------------
# Engine integration tests (with DB)
# ---------------------------------------------------------------------------


class TestEngineExecution:
    """Execute semantic queries against PostgreSQL."""

    def test_total_doctors_empty_db(self, db_session: Session) -> None:
        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="total_doctors"))
        assert result.row_count == 1
        assert result.rows[0]["total"] == 0

    def test_total_doctors_with_data(self, db_session: Session) -> None:
        now = datetime.now(UTC)
        db_session.add_all([
            DoctorModel(id="d1", name="Dr. A", normalized_name="dr. a", sex="male", active=True, service_active=True, whatsapp_phone="1111111111", created_at=now, updated_at=now),
            DoctorModel(id="d2", name="Dr. B", normalized_name="dr. b", sex="female", active=True, service_active=True, whatsapp_phone="2222222222", created_at=now, updated_at=now),
            DoctorModel(id="d3", name="Dr. C", normalized_name="dr. c", sex="male", active=True, service_active=False, whatsapp_phone="3333333333", created_at=now, updated_at=now),
        ])
        db_session.commit()

        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="total_doctors"))
        assert result.row_count == 1
        assert result.rows[0]["total"] == 2  # only active + service_active

    def test_doctors_by_sex_with_data(self, db_session: Session) -> None:
        now = datetime.now(UTC)
        db_session.add_all([
            DoctorModel(id="d1", name="Dr. A", normalized_name="dr. a", sex="male", active=True, service_active=True, whatsapp_phone="1111111111", created_at=now, updated_at=now),
            DoctorModel(id="d2", name="Dr. B", normalized_name="dr. b", sex="female", active=True, service_active=True, whatsapp_phone="2222222222", created_at=now, updated_at=now),
            DoctorModel(id="d3", name="Dr. C", normalized_name="dr. c", sex="male", active=True, service_active=True, whatsapp_phone="3333333333", created_at=now, updated_at=now),
        ])
        db_session.commit()

        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="doctors_by_sex"))
        rows = {r["sex"]: r["total"] for r in result.rows}
        assert rows.get("male") == 2
        assert rows.get("female") == 1

    def test_duplicate_doctor_names(self, db_session: Session) -> None:
        now = datetime.now(UTC)
        db_session.add_all([
            DoctorModel(id="d1", name="Dr. Perez", normalized_name="dr. perez 1", sex="male", active=True, service_active=True, whatsapp_phone="1111111111", created_at=now, updated_at=now),
            DoctorModel(id="d2", name="Dr. Perez", normalized_name="dr. perez 2", sex="male", active=True, service_active=True, whatsapp_phone="2222222222", created_at=now, updated_at=now),
            DoctorModel(id="d3", name="Dr. Gomez", normalized_name="dr. gomez", sex="female", active=True, service_active=True, whatsapp_phone="3333333333", created_at=now, updated_at=now),
        ])
        db_session.commit()

        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="duplicate_doctor_names"))
        assert result.row_count == 1
        assert result.rows[0]["name"] == "Dr. Perez"
        assert result.rows[0]["occurrences"] == 2

    def test_last_service_by_doctor(self, db_session: Session) -> None:
        """Verify the 'last service' metric generates correct SQL."""
        now = datetime.now(UTC)
        db_session.add(DoctorModel(id="d1", name="Dr. A", normalized_name="dr. a", sex="male", active=True, service_active=True, whatsapp_phone="1111111111", created_at=now, updated_at=now))
        db_session.add(CalendarModel(id="c1", year=2026, month=5, status="approved", created_at=now, updated_at=now))
        db_session.add(CalendarVersionModel(id="cv1", calendar_id="c1", version_number=1, status="approved", created_at=now))
        db_session.add(ServiceAreaModel(id="sa1", code="urgencias", display_name="Urgencias", load_weight=10, start_hour=7, created_at=now, updated_at=now))
        # SQLAlchemy ordena los INSERT por relationship(), no por ForeignKey suelto:
        # sin este flush insertaría la asignación antes que la versión de
        # calendario y PostgreSQL rechazaría la FK (SQLite no la validaba).
        db_session.flush()
        db_session.add(CalendarAssignmentModel(id="ca1", calendar_version_id="cv1", service_date=date(2026, 5, 15), service_area_id="sa1", doctor_id="d1", created_at=now))
        db_session.commit()

        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="last_service_by_doctor"))
        assert result.row_count == 1
        assert result.rows[0]["doctor"] == "Dr. A"
        # `MAX(ca.service_date)` devuelve un `date` real en PostgreSQL; SQLite
        # devolvía el texto "2026-05-15" porque guarda las fechas como TEXT.
        # El valor es el mismo y el formateo para el usuario no cambia.
        assert result.rows[0]["ultimo_servicio"] == date(2026, 5, 15)


# ---------------------------------------------------------------------------
# Every declared filter / dimension must produce SQL that PostgreSQL accepts
#
# El bug que motivó esta red: `_build_where()` armaba el WHERE con la CLAVE de
# la dimensión (`rank`) en vez de su expresión SQL (`r.name`), así que cualquier
# filtro generaba SQL inválido. El error quedaba tragado aguas arriba y el
# usuario recibía el número SIN filtrar — creíble y falso.
#
# Estos tests recorren METRICS y ejecutan de verdad cada filtro y cada dimensión
# declarados. Una métrica no puede declarar algo que su FROM no soporte: si lo
# declara, tiene que correr.
# ---------------------------------------------------------------------------

# Valor de ejemplo por cada campo filtrable declarado en METRICS. Si una métrica
# nueva declara un filtro sin muestra aquí, el test de cobertura falla y obliga a
# decidir qué SQL debería generar ese filtro.
_FILTER_SAMPLES: dict[str, tuple[str, Any]] = {
    "sex": ("eq", "male"),
    "rank": ("eq", "Sargento"),
    "department": ("eq", "Emergencia"),
    "service_area": ("eq", "Urgencias"),
    "doctor": ("like", "Perez"),
    "status": ("eq", "confirmed"),
    "date": ("between", [date(2026, 5, 1), date(2026, 5, 31)]),
    "mission_date": ("gte", date(2026, 5, 1)),
    "month": ("eq", 5),
    "year": ("eq", 2026),
    "confirmation_type": ("eq", "mission"),
}

_FILTER_CASES = [
    pytest.param(
        metric_name,
        field,
        *_FILTER_SAMPLES[field],
        id=f"{metric_name}__{field}",
    )
    for metric_name, metric in sorted(METRICS.items())
    for field in sorted(metric.supported_filters)
    if field in _FILTER_SAMPLES
]

_DIMENSION_CASES = [
    pytest.param(metric_name, dim, id=f"{metric_name}__{dim}")
    for metric_name, metric in sorted(METRICS.items())
    for dim in sorted(metric.supported_dimensions)
]


class TestDeclaredFiltersAndDimensionsRun:
    def test_every_declared_filter_has_a_sample(self) -> None:
        """Un filtro declarado sin muestra quedaría fuera de la red sin avisar."""
        declared = {f for m in METRICS.values() for f in m.supported_filters}
        assert declared <= set(_FILTER_SAMPLES), (
            f"Filtros declarados sin muestra de prueba: {declared - set(_FILTER_SAMPLES)}"
        )

    @pytest.mark.parametrize("metric_name,field,operator,value", _FILTER_CASES)
    def test_filter_runs(
        self,
        db_session: Session,
        metric_name: str,
        field: str,
        operator: str,
        value: Any,
    ) -> None:
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(
            metric=metric_name,
            filters=[Filter(field=field, operator=operator, value=value)],
        )
        result = engine.execute(sq)
        assert result.metric_name == metric_name

    @pytest.mark.parametrize("metric_name,dimension", _DIMENSION_CASES)
    def test_dimension_runs(
        self, db_session: Session, metric_name: str, dimension: str
    ) -> None:
        engine = SemanticLayerEngine(db_session)
        sq = SemanticQuery(metric=metric_name, dimensions=[dimension])
        result = engine.execute(sq)
        assert result.metric_name == metric_name


# ---------------------------------------------------------------------------
# El filtro tiene que cambiar el resultado, no sólo compilar
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded(db_session: Session) -> None:
    """3 médicos, 2 rangos y 3 asignaciones repartidas en 2 áreas."""
    now = datetime.now(UTC)
    db_session.add_all([
        RankModel(id="r1", name="Sargento", normalized_name="sargento",
                  abbreviation="SG", created_at=now, updated_at=now),
        RankModel(id="r2", name="Cabo", normalized_name="cabo",
                  abbreviation="CB", created_at=now, updated_at=now),
    ])
    db_session.add_all([
        DoctorModel(id="d1", name="Dr. A", normalized_name="dr. a", sex="male",
                    rank_id="r1", active=True, service_active=True,
                    whatsapp_phone="1111111111", created_at=now, updated_at=now),
        DoctorModel(id="d2", name="Dr. B", normalized_name="dr. b", sex="female",
                    rank_id="r1", active=True, service_active=True,
                    whatsapp_phone="2222222222", created_at=now, updated_at=now),
        DoctorModel(id="d3", name="Dr. C", normalized_name="dr. c", sex="male",
                    rank_id="r2", active=True, service_active=True,
                    whatsapp_phone="3333333333", created_at=now, updated_at=now),
    ])
    db_session.add(CalendarModel(id="c1", year=2026, month=5, status="approved",
                                 created_at=now, updated_at=now))
    db_session.add(CalendarVersionModel(id="cv1", calendar_id="c1", version_number=1,
                                        status="approved", created_at=now))
    db_session.add_all([
        ServiceAreaModel(id="sa1", code="urgencias", display_name="Urgencias",
                         load_weight=10, start_hour=7, created_at=now, updated_at=now),
        ServiceAreaModel(id="sa2", code="emergencia", display_name="Emergencia",
                         load_weight=10, start_hour=7, created_at=now, updated_at=now),
    ])
    # SQLAlchemy ordena los INSERT por relationship(), no por ForeignKey suelto:
    # las asignaciones tienen que ir después de sus tres padres.
    db_session.flush()
    db_session.add_all([
        CalendarAssignmentModel(id="ca1", calendar_version_id="cv1",
                                service_date=date(2026, 5, 15), service_area_id="sa1",
                                doctor_id="d1", created_at=now),
        CalendarAssignmentModel(id="ca2", calendar_version_id="cv1",
                                service_date=date(2026, 5, 16), service_area_id="sa2",
                                doctor_id="d2", created_at=now),
        CalendarAssignmentModel(id="ca3", calendar_version_id="cv1",
                                service_date=date(2026, 5, 17), service_area_id="sa1",
                                doctor_id="d3", created_at=now),
    ])
    db_session.commit()


def _total(db_session: Session, metric: str, filters: list[Filter]) -> int:
    """El conteo de la única fila: estas métricas devuelven un solo número."""
    result = SemanticLayerEngine(db_session).execute(
        SemanticQuery(metric=metric, filters=filters)
    )
    fila = result.rows[0]
    return fila.get("total", fila.get("total_servicios"))


class TestFiltersActuallyFilter:
    """Sin filtro y con filtro tienen que dar números distintos.

    El bug original devolvía el mismo total en ambos casos: el filtro se perdía
    en un error tragado aguas arriba y el usuario recibía un número creíble.
    """

    def test_sex_filter_narrows_the_count(self, db_session: Session, seeded: None) -> None:
        assert _total(db_session, "total_doctors", []) == 3
        hombres = _total(
            db_session, "total_doctors", [Filter("sex", "eq", "male")]
        )
        assert hombres == 2

    def test_rank_filter_narrows_the_count(self, db_session: Session, seeded: None) -> None:
        sargentos = _total(
            db_session, "total_doctors", [Filter("rank", "eq", "Sargento")]
        )
        assert sargentos == 2

    def test_unknown_rank_returns_zero_not_everyone(
        self, db_session: Session, seeded: None
    ) -> None:
        """«Cuántos pasantes tengo» no puede devolver el total de médicos."""
        assert _total(db_session, "total_doctors", [Filter("rank", "eq", "Pasante")]) == 0

    def test_service_area_filter_narrows_services(
        self, db_session: Session, seeded: None
    ) -> None:
        assert _total(db_session, "total_services", []) == 3
        urgencias = _total(
            db_session, "total_services", [Filter("service_area", "eq", "Urgencias")]
        )
        assert urgencias == 2

    def test_date_filter_narrows_services(self, db_session: Session, seeded: None) -> None:
        en_rango = _total(
            db_session,
            "total_services",
            [Filter("date", "between", [date(2026, 5, 16), date(2026, 5, 17)])],
        )
        assert en_rango == 2

    def test_filter_parameter_reaches_the_query(
        self, db_session: Session, seeded: None
    ) -> None:
        """El valor tiene que viajar como parámetro ligado, no perderse."""
        result = SemanticLayerEngine(db_session).execute(
            SemanticQuery(metric="total_doctors", filters=[Filter("sex", "eq", "male")])
        )
        assert "male" in result.params.values()
        assert "d.sex" in result.sql


# ---------------------------------------------------------------------------
# Resolver tests
# ---------------------------------------------------------------------------


class TestResolverMapping:
    """SemanticLayerResolver maps user intents to SemanticQueries."""

    def test_resolve_doctor_count(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        result = resolver.resolve(
            user_text="cuantos medicos hay",
            domain="medicos",
            action="contar",
            entities={},
        )
        assert result is not None
        assert result.metric_name == "total_doctors"

    def test_resolve_doctors_by_sex(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        result = resolver.resolve(
            user_text="cuantos medicos hombres hay",
            domain="medicos",
            action="contar",
            entities={"sexo": "male"},
        )
        assert result is not None
        assert result.metric_name == "doctors_by_sex"

    def test_resolve_mission_ranking(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        result = resolver.resolve(
            user_text="dame el ranking de misiones",
            domain="ranking",
            action="listar",
            entities={},
        )
        assert result is not None
        assert result.metric_name == "mission_ranking"

    def test_resolve_last_service(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        result = resolver.resolve(
            user_text="ultimo servicio de los medicos",
            domain="medicos",
            action="consultar",
            entities={},
        )
        assert result is not None
        assert result.metric_name == "last_service_by_doctor"

    def test_resolve_unknown_domain_returns_none(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        result = resolver.resolve(
            user_text="cual es el clima hoy",
            domain="clima",
            action="consultar",
            entities={},
        )
        assert result is None

    def test_is_semantic_query_detects_supported(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        assert resolver.is_semantic_query("medicos", "contar", {}) is True
        assert resolver.is_semantic_query("calendario", "listar", {}) is True
        assert resolver.is_semantic_query("clima", "consultar", {}) is False
        assert resolver.is_semantic_query("general", "preguntar", {}) is False


# ---------------------------------------------------------------------------
# Resolver → AgentResult conversion
# ---------------------------------------------------------------------------


class TestResolverToAgentResult:
    """Conversion from SemanticResult to AgentResult."""

    def test_empty_result(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        from backend.app.application.telegram.semantic_layer.models import SemanticResult

        sr = SemanticResult(
            columns=["total"],
            rows=[],
            sql="SELECT 1",
            params={},
            row_count=0,
            metric_name="total_doctors",
        )
        ar = resolver.to_agent_result(sr)
        assert "No se encontraron resultados" in ar.response_text

    def test_non_empty_result(self, db_session: Session) -> None:
        resolver = SemanticLayerResolver(db_session)
        from backend.app.application.telegram.semantic_layer.models import SemanticResult

        sr = SemanticResult(
            columns=["total"],
            rows=[{"total": 42}],
            sql="SELECT 42 AS total",
            params={},
            row_count=1,
            metric_name="total_doctors",
        )
        ar = resolver.to_agent_result(sr)
        assert "42" in ar.response_text
        assert ar.agent_action == "query"
        assert ar.tool_entities is not None
        assert ar.tool_entities.get("metric") == "total_doctors"
