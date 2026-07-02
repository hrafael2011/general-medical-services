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
