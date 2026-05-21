"""Content sanitization for agent responses — strips HTML/XML tags."""
import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]*>")


def sanitize_text(value: str | None) -> str:
    """Strip HTML/XML tags from *value*. Returns empty string for None."""
    if value is None:
        return ""
    return _TAG_RE.sub("", str(value)).strip()


_VALUE_LABELS: dict[str, dict[Any, str]] = {
    "sex": {
        "male": "Masculino",
        "female": "Femenino",
    },
    "status": {
        "draft": "Borrador",
        "approved": "Aprobado",
        "confirmed": "Confirmado",
        "pending": "Pendiente",
        "cancelled": "Cancelado",
    },
    "calendar_status": {
        "draft": "Borrador",
        "approved": "Aprobado",
    },
    "availability_mode": {
        "monthly": "Mensual",
        "weekly": "Semanal",
        "fixed": "Fijo",
        "variable": "Variable",
    },
    "active": {
        True: "Sí",
        False: "No",
    },
    "service_active": {
        True: "Sí",
        False: "No",
    },
    "eligible": {
        True: "Sí",
        False: "No",
    },
}


def display_value(column: str, value: Any) -> str:
    """Return a sanitized, user-facing Spanish value for a DB cell."""
    if value is None:
        return ""
    labels = _VALUE_LABELS.get(column)
    if labels and value in labels:
        return labels[value]
    if isinstance(value, bool):
        return "Sí" if value else "No"
    return sanitize_text(str(value))


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _is_uuid_column(rows: list[dict[str, Any]], column: str) -> bool:
    """True when *column* exposes UUID values across sampled rows."""
    if not rows:
        return False
    samples = [
        row.get(column) for row in rows[:5]
        if row.get(column) is not None
    ]
    if not samples:
        return False
    return all(
        isinstance(v, str) and bool(_UUID_RE.search(v))
        for v in samples
    )


def _public_columns(columns: list[str]) -> list[str]:
    """Filter out internal ID columns not useful to end users."""
    return [
        c for c in columns
        if c.lower() != "id" and not c.lower().endswith("_id")
    ]


_METADATA_COLUMNS = {
    "year", "month", "period_year", "period_month",
    "ranking_position", "created_at", "updated_at",
}


def _column_sort_key(col: str) -> tuple[int, str]:
    """Metadata columns last, informative columns first."""
    return (0 if col.lower() not in _METADATA_COLUMNS else 1, col.lower())


def _informative_columns(columns: list[str]) -> list[str]:
    """Reorder so informative columns come before metadata (year, month, position)."""
    return sorted(columns, key=_column_sort_key)


def format_rows(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Format query results as human-readable Telegram text.

    Strips internal ID columns, shows up to 5 columns per row.
    """
    cols = _informative_columns(_public_columns(columns))
    # Remove columns whose values are all UUIDs
    cols = [c for c in cols if not _is_uuid_column(rows, c)]
    if not cols:
        return "No se encontraron resultados."

    filtered = [{c: row.get(c) for c in cols} for row in rows]
    count = len(filtered)
    max_cols = 5

    if count == 0:
        return "No se encontraron resultados."
    if count == 1:
        first = filtered[0]
        parts = [f"{k}: {display_value(k, v)}" for k, v in first.items() if v is not None]
        return "Resultado: " + " | ".join(parts)
    if count <= 5:
        lines = [
            f"{i+1}. " + " | ".join(
                display_value(c, r.get(c, "")) for c in cols[:max_cols]
            )
            for i, r in enumerate(filtered)
        ]
        return f"Se encontraron {count} resultados:\n" + "\n".join(lines)

    lines = [
        f"{i+1}. " + " | ".join(
            display_value(c, r.get(c, "")) for c in cols[:max_cols]
        )
        for i, r in enumerate(filtered[:5])
    ]
    return f"Se encontraron {count} resultados. Los primeros:\n" + "\n".join(lines)
