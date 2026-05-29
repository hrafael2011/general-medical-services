"""Semantic-layer registry helpers.

Convenience module to expose metric/dimension catalogues to the
ConversationalAgent so it can inject them into the LLM system prompt.
"""

from __future__ import annotations

from typing import Any

from .definitions import DIMENSIONS, METRICS


def get_metric_catalogue() -> str:
    """Return a structured text block describing all available metrics.

    Suitable for injection into an LLM system prompt.
    """
    lines: list[str] = ["=== AVAILABLE METRICS ===", ""]
    for m in METRICS.values():
        lines.append(f"- {m.name}: {m.display_name}")
        lines.append(f"  Description: {m.description}")
        if m.supported_dimensions:
            lines.append(f"  Dimensions: {', '.join(sorted(m.supported_dimensions))}")
        if m.supported_filters:
            lines.append(f"  Filters: {', '.join(sorted(m.supported_filters))}")
        lines.append("")
    return "\n".join(lines)


def get_dimension_catalogue() -> str:
    """Return a structured text block describing all available dimensions."""
    lines: list[str] = ["=== AVAILABLE DIMENSIONS ===", ""]
    for d in DIMENSIONS.values():
        lines.append(f"- {d.name}: {d.display_name}")
    return "\n".join(lines)


def get_full_catalogue() -> str:
    """Return both metric and dimension catalogues."""
    return get_metric_catalogue() + "\n" + get_dimension_catalogue()


def find_metric_by_name(name: str) -> dict[str, Any] | None:
    """Find a metric definition by its internal name."""
    m = METRICS.get(name)
    if m is None:
        return None
    return {
        "name": m.name,
        "display_name": m.display_name,
        "description": m.description,
        "dimensions": sorted(m.supported_dimensions),
        "filters": sorted(m.supported_filters),
    }


def find_dimension_by_name(name: str) -> dict[str, Any] | None:
    """Find a dimension definition by its internal name."""
    d = DIMENSIONS.get(name)
    if d is None:
        return None
    return {"name": d.name, "display_name": d.display_name}
