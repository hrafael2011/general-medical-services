"""Tests for the Semantic Layer deterministic query engine."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import uuid

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
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
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
    """Execute semantic queries against an in-memory SQLite DB."""

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
        db_session.add(CalendarAssignmentModel(id="ca1", calendar_version_id="cv1", service_date=date(2026, 5, 15), service_area_id="sa1", doctor_id="d1", created_at=now))
        db_session.commit()

        engine = SemanticLayerEngine(db_session)
        result = engine.execute(SemanticQuery(metric="last_service_by_doctor"))
        assert result.row_count == 1
        assert result.rows[0]["doctor"] == "Dr. A"
        assert result.rows[0]["ultimo_servicio"] == "2026-05-15"


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
