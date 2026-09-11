"""Tests for OperationalQueryHandler."""

from unittest.mock import MagicMock

import pytest

from backend.app.application.telegram.operational_query_handler import (
    OperationalQueryHandler,
    OperationalResult,
)


class DummyResult:
    """Minimal result-like object for testing."""
    def __init__(self, ok=True, data=None, response_text="ok",
                 match_type="semantic_layer", columns=None, rows=None):
        self.ok = ok
        self.data = data or {}
        self.response_text = response_text
        self.match_type = match_type
        self.columns = columns or []
        self.rows = rows or []


class TestOperationalResult:
    def test_immutable_dataclass(self):
        r = OperationalResult(
            ok=True,
            match_type="semantic_layer",
            response_text="test",
        )
        assert r.ok is True
        assert r.match_type == "semantic_layer"
        assert r.response_text == "test"
        assert r.used_sql is False
        assert r.used_llm is False
        assert r.fallback_reason is None


class TestOperationalQueryHandler:
    def test_try_semantic_layer_returns_when_matched(self):
        resolver = MagicMock()
        resolver.resolve.return_value = DummyResult(
            ok=True, response_text="42 médicos", match_type="semantic_layer"
        )
        handler = OperationalQueryHandler(
            semantic_layer=resolver,
            doctor_service=None,
            calendar_service=None,
            intent_router=None,
            sql_executor=None,
            llm_provider=None,
        )
        result = handler.try_semantic_layer(
            user_text="cuantos medicos hay",
            domain="medicos",
            action="count",
            entities={},
        )
        assert result is not None
        assert result.ok is True
        assert result.match_type == "semantic_layer"
        assert not result.used_sql

    def test_try_semantic_layer_returns_none_when_not_handled(self):
        resolver = MagicMock()
        resolver.resolve.return_value = None  # semantic layer can't handle
        handler = OperationalQueryHandler(
            semantic_layer=resolver,
            doctor_service=None,
            calendar_service=None,
            intent_router=None,
            sql_executor=None,
            llm_provider=None,
        )
        result = handler.try_semantic_layer(
            user_text="dato no soportado",
            domain="unknown",
            action="query",
            entities={},
        )
        assert result is None

    def test_resolve_runs_full_pipeline(self):
        resolver = MagicMock()
        resolver.is_semantic_query.return_value = True
        resolver.resolve.return_value = DummyResult(
            ok=True, response_text="42 médicos", match_type="semantic_layer"
        )
        handler = OperationalQueryHandler(
            semantic_layer=resolver,
            doctor_service=MagicMock(),
            calendar_service=MagicMock(),
            intent_router=MagicMock(),
            sql_executor=MagicMock(),
            llm_provider=None,
        )
        result = handler.resolve(
            user_text="cuantos medicos hay",
            domain="medicos",
            action="count",
            entities={},
            telegram_user_id="123",
        )
        assert result is not None
        assert result.ok is True
        assert result.match_type == "semantic_layer"

    def test_full_pipeline_falls_through_to_sql(self):
        resolver = MagicMock()
        resolver.is_semantic_query.return_value = True
        resolver.resolve.return_value = None
        doctor_svc = MagicMock()
        doctor_svc.execute.return_value = None
        calendar_svc = MagicMock()
        calendar_svc.execute.return_value = None
        router = MagicMock()
        router.handle.return_value = None
        sql_executor = MagicMock()
        sql_executor.execute.return_value = {
            "ok": True,
            "data": {"columns": ["result"], "rows": [{"result": "42"}], "row_count": 1},
        }

        handler = OperationalQueryHandler(
            semantic_layer=resolver,
            doctor_service=doctor_svc,
            calendar_service=calendar_svc,
            intent_router=router,
            sql_executor=sql_executor,
            llm_provider=None,
        )
        result = handler.resolve(
            user_text="algo que solo sql sabe",
            domain="medicos",
            action="count",
            entities={},
            telegram_user_id="123",
        )
        assert result is not None
        assert result.used_sql is True
        assert result.match_type == "sql_fallback"

    def test_empty_sql_result_returns_error(self):
        resolver = MagicMock()
        resolver.is_semantic_query.return_value = True
        resolver.resolve.return_value = None
        sql_executor = MagicMock()
        sql_executor.execute.return_value = {
            "ok": False,
            "error": "query failed",
        }
        handler = OperationalQueryHandler(
            semantic_layer=resolver,
            doctor_service=None,
            calendar_service=None,
            intent_router=None,
            sql_executor=sql_executor,
            llm_provider=None,
        )
        result = handler.resolve(
            user_text="query fallida",
            domain="medicos",
            action="query",
            entities={},
            telegram_user_id="123",
        )
        assert result is not None
        assert result.ok is False

    def test_format_sql_single_result(self):
        handler = OperationalQueryHandler(
            semantic_layer=None, doctor_service=None, calendar_service=None,
            intent_router=None, sql_executor=None,
        )
        rows = [{"result": "42"}]
        cols = ["result"]
        text = handler._format_sql_result(rows, cols)
        assert "Resultado" in text
        assert "42" in text

    def test_format_sql_multi_result(self):
        handler = OperationalQueryHandler(
            semantic_layer=None, doctor_service=None, calendar_service=None,
            intent_router=None, sql_executor=None,
        )
        rows = [
            {"name": "Ana", "rank": "Mayor"},
            {"name": "Luis", "rank": "Cabo"},
            {"name": "Pedro", "rank": "Sargento"},
        ]
        cols = ["name", "rank"]
        text = handler._format_sql_result(rows, cols)
        assert "3 resultados" in text
        assert "Ana" in text
        assert "Luis" in text


class TestDominioManda:
    """La decisión del NLU (`domain`) decide quién responde, no el orden fijo.

    Regresión del caso reportado: «Que medicos estan de servicio el 3 de
    agosto». El NLU elige `calendar_assignments` → domain="calendario", pero
    `resolve()` llamaba a `doctor_service.execute()` sin mirar el dominio.
    Como `_filters_from_resolved` devuelve {} (no None), ese servicio nunca
    devolvía None y respondía él con TODOS los médicos (41) en vez de los
    asignados a la fecha.
    """

    def _handler(self, *, doctor_service, calendar_service=None):
        return OperationalQueryHandler(
            semantic_layer=None,
            doctor_service=doctor_service,
            calendar_service=calendar_service,
            intent_router=None,
            sql_executor=None,
            llm_provider=None,
        )

    def test_dominio_no_medicos_no_lo_responde_el_servicio_de_medicos(self):
        """Con domain="calendario" el servicio de médicos no debe ejecutarse."""
        doctor_service = MagicMock()
        doctor_service.execute.return_value = DummyResult(
            ok=True,
            response_text="Se encontraron 41 resultados. Los primeros: ...",
            match_type="doctor_service",
        )
        handler = self._handler(doctor_service=doctor_service)

        handler.resolve(
            user_text="Que medicos estan de servicio el 3 de agosto",
            domain="calendario",
            action="query",
            entities={"start_date": "2026-08-03", "end_date": "2026-08-03"},
        )

        doctor_service.execute.assert_not_called()

    def test_dominio_medicos_si_lo_responde_el_servicio_de_medicos(self):
        """La contracara: con domain="medicos" sí responde (no romper lo que anda)."""
        doctor_service = MagicMock()
        doctor_service.execute.return_value = DummyResult(
            ok=True, response_text="40 médicos activos", match_type="doctor_service"
        )
        handler = self._handler(doctor_service=doctor_service)

        result = handler.resolve(
            user_text="Cuantos medicos hay",
            domain="medicos",
            action="count",
            entities={},
        )

        doctor_service.execute.assert_called_once()
        assert result is not None
        assert "40" in result.response_text


class TestCalendarQueryWithoutDates:
    """Una pregunta de calendario sin fechas no puede reventar.

    `_detect_calendar_query` mandaba TODA frase con «calendario» que no dijera
    «estado» a `list_calendar_assignments_by_date_range`, que indexa
    `params["start_date"]` sin defensa. Frases como «Hay calendario de junio
    2026?» no traen rango de fechas: la consulta moría con KeyError y el usuario
    no recibía nada. Once turnos del corpus caían exactamente acá.
    """

    def _handler(self, calendar_service):
        return OperationalQueryHandler(
            semantic_layer=None,
            doctor_service=None,
            calendar_service=calendar_service,
            intent_router=None,
            sql_executor=None,
            llm_provider=None,
        )

    def test_question_about_a_month_answers_status_without_crashing(self, db_session):
        from backend.app.application.telegram.calendar_query_service import (
            CalendarQueryService,
        )

        handler = self._handler(CalendarQueryService(db_session))

        result = handler.resolve(
            user_text="Hay calendario de junio 2026?",
            domain="calendario",
            action="query",
            entities={"month": 6, "year": 2026},
        )

        # Antes se abstenía para no reventar con el `params["start_date"]` sin
        # defensa. La pregunta es de existencia, no de rango: se contesta con el
        # estado del calendario (y sigue sin reventar).
        assert result is not None
        assert result.match_type == "calendar_service"
        assert "calendario" in result.response_text.lower()

    def test_a_real_date_range_still_lists_assignments(self):
        """La contracara: con fechas de verdad, el listado por rango sigue vivo."""
        handler = self._handler(MagicMock())

        query_type = handler._detect_calendar_query(
            "Dame las guardias del calendario del 1 al 15 de julio",
            {"start_date": "2026-07-01", "end_date": "2026-07-15"},
        )

        assert query_type == "list_calendar_assignments_by_date_range"

    def test_asking_about_estado_keeps_its_own_query(self):
        """«estado» no depende de las fechas y no debe cambiar de rama."""
        handler = self._handler(MagicMock())

        assert (
            handler._detect_calendar_query("Cual es el estado del calendario de julio?", {})
            == "calendar_status"
        )

    def test_un_rango_a_medias_no_alcanza(self):
        """Con una sola punta del rango no hay rango que listar."""
        handler = self._handler(MagicMock())

        assert (
            handler._detect_calendar_query(
                "Dame las guardias del calendario", {"start_date": "2026-07-01"}
            )
            is None
        )
