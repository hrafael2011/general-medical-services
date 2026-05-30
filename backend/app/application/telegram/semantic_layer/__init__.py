"""Semantic Layer for deterministic business-query execution.

The semantic layer translates natural-language business questions into
hand-written, validated SQL templates.  No LLM is involved in SQL generation,
guaranteeing 100% accuracy for covered queries.

Usage::

    from app.application.telegram.semantic_layer import SemanticLayerResolver
    resolver = SemanticLayerResolver(db_session)
    result = resolver.resolve(
        user_text="¿Cuántos médicos hay?",
        domain="medicos",
        action="contar",
        entities={},
    )
    # result is a SemanticResult with columns, rows, and the generated SQL.
"""

from .definitions import DIMENSIONS, METRICS
from .engine import SemanticLayerEngine
from .models import Filter, Metric, Dimension, SemanticQuery, SemanticResult
from .registry import find_dimension_by_name, find_metric_by_name, get_full_catalogue
from .resolver import SemanticLayerResolver

__all__ = [
    "Dimension",
    "Filter",
    "Metric",
    "SemanticLayerEngine",
    "SemanticLayerResolver",
    "SemanticQuery",
    "SemanticResult",
    "DIMENSIONS",
    "METRICS",
    "find_dimension_by_name",
    "find_metric_by_name",
    "get_full_catalogue",
]
