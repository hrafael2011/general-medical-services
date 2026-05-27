"""Core dataclasses for the Semantic Layer.

The Semantic Layer translates business-meaningful queries (metrics, dimensions,
filter) into deterministic SQL.  It never lets an LLM write raw SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Filter:
    """A business filter applied to a SemanticQuery."""

    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class SemanticQuery:
    """User-facing business query.

    This is what the ConversationalAgent builds after interpreting the user's
    intent.  It contains *what* the user wants, not *how* to get it.
    """

    metric: str
    dimensions: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    order_by: list[tuple[str, str]] = field(default_factory=list)
    limit: int | None = None
    format: str | None = None

    def add_filter(self, field: str, operator: str, value: Any) -> SemanticQuery:
        """Return a new query with an additional filter."""
        return SemanticQuery(
            metric=self.metric,
            dimensions=list(self.dimensions),
            filters=[*self.filters, Filter(field, operator, value)],
            order_by=list(self.order_by),
            limit=self.limit,
            format=self.format,
        )


@dataclass(frozen=True)
class Dimension:
    """A dimension along which a metric can be sliced / grouped."""

    name: str
    display_name: str
    sql_expression: str
    supported_metrics: set[str] | None = None


@dataclass(frozen=True)
class Metric:
    """A business metric definition.

    Each metric carries a *template* function that receives the concrete
    ``SemanticQuery`` and returns the final SQL string together with the
    bound parameters.  The template is pure Python — no LLM involved.
    """

    name: str
    display_name: str
    description: str
    sql_template: Callable[[SemanticQuery], tuple[str, dict[str, Any]]]
    supported_dimensions: set[str] = field(default_factory=set)
    supported_filters: set[str] = field(default_factory=set)
    default_order_by: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class SemanticResult:
    """Result of executing a SemanticQuery through the SemanticLayerEngine."""

    columns: list[str]
    rows: list[dict[str, Any]]
    sql: str
    params: dict[str, Any]
    row_count: int
    truncated: bool = False
    metric_name: str = ""
    dimensions: list[str] = field(default_factory=list)
