"""SemanticLayerEngine — deterministic SQL generation and execution.

Given a ``SemanticQuery`` the engine:

1. Validates the metric exists.
2. Validates dimensions / filters are supported by the metric.
3. Calls the metric's hand-written ``sql_template`` to obtain SQL + params.
4. Executes safely via SQLAlchemy ``text()``.
5. Returns a ``SemanticResult``.

No LLM is involved in SQL generation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .definitions import DIMENSIONS, METRICS
from .models import Filter, SemanticQuery, SemanticResult


class SemanticLayerError(Exception):
    """Base exception for semantic-layer related failures."""


class UnsupportedMetricError(SemanticLayerError):
    """The requested metric does not exist."""


class UnsupportedDimensionError(SemanticLayerError):
    """One or more dimensions are not supported by the metric."""


class UnsupportedFilterError(SemanticLayerError):
    """One or more filters are not supported by the metric."""


class SemanticLayerEngine:
    """Deterministic query engine for the semantic layer."""

    def __init__(self, session: Session, max_rows: int = 100) -> None:
        self.session = session
        self.max_rows = max_rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(self, query: SemanticQuery) -> SemanticResult:
        """Execute a semantic query and return results.

        Raises:
            UnsupportedMetricError: if the metric is not defined.
            UnsupportedDimensionError: if a dimension is not supported.
            UnsupportedFilterError: if a filter field is not supported.
        """
        metric = self._resolve_metric(query.metric)
        self._validate_dimensions(metric, query.dimensions)
        self._validate_filters(metric, query.filters)

        sql, params = metric.sql_template(query)
        rows, columns, truncated = self._run_sql(sql, params)

        return SemanticResult(
            columns=columns,
            rows=rows,
            sql=sql,
            params=params,
            row_count=len(rows),
            truncated=truncated,
            metric_name=metric.name,
            dimensions=query.dimensions,
        )

    def list_metrics(self) -> list[dict[str, Any]]:
        """Return a human-readable list of available metrics."""
        return [
            {
                "name": m.name,
                "display_name": m.display_name,
                "description": m.description,
                "dimensions": sorted(m.supported_dimensions),
                "filters": sorted(m.supported_filters),
            }
            for m in METRICS.values()
        ]

    def list_dimensions(self) -> list[dict[str, Any]]:
        """Return a human-readable list of available dimensions."""
        return [
            {"name": d.name, "display_name": d.display_name}
            for d in DIMENSIONS.values()
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_metric(self, name: str) -> Any:
        metric = METRICS.get(name)
        if metric is None:
            raise UnsupportedMetricError(f"Metric '{name}' is not defined.")
        return metric

    def _validate_dimensions(self, metric: Any, dimensions: list[str]) -> None:
        if not dimensions:
            return
        unsupported = set(dimensions) - metric.supported_dimensions
        if unsupported:
            raise UnsupportedDimensionError(
                f"Metric '{metric.name}' does not support dimensions: {unsupported}. "
                f"Supported: {metric.supported_dimensions}"
            )

    def _validate_filters(self, metric: Any, filters: list[Filter]) -> None:
        if not filters:
            return
        unsupported = {f.field for f in filters} - metric.supported_filters
        if unsupported:
            raise UnsupportedFilterError(
                f"Metric '{metric.name}' does not support filters: {unsupported}. "
                f"Supported: {metric.supported_filters}"
            )

    def _run_sql(
        self, sql: str, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[str], bool]:
        """Execute SQL safely via SQLAlchemy and return rows + columns."""
        result = self.session.execute(text(sql), params)
        columns = list(result.keys())

        rows: list[dict[str, Any]] = []
        truncated = False
        for idx, row in enumerate(result.mappings()):
            if idx >= self.max_rows:
                truncated = True
                break
            rows.append(dict(row))

        return rows, columns, truncated
