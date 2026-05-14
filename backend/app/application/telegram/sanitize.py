"""Content sanitization for agent responses — strips HTML/XML tags."""
import re
from typing import Any

_TAG_RE = re.compile(r"<[^>]*>")


def sanitize_text(value: str | None) -> str:
    """Strip HTML/XML tags from *value*. Returns empty string for None."""
    if value is None:
        return ""
    return _TAG_RE.sub("", str(value)).strip()


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _public_columns(columns: list[str]) -> list[str]:
    """Filter out internal ID columns not useful to end users."""
    return [
        c for c in columns
        if c.lower() != "id" and not c.lower().endswith("_id")
    ]


def format_rows(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Format query results as human-readable Telegram text.

    Strips internal ID columns, truncates wide results to 5 rows and
    3 columns per row.
    """
    cols = _public_columns(columns)
    if not cols:
        return "No se encontraron resultados."

    filtered = [{c: row.get(c) for c in cols} for row in rows]
    count = len(filtered)

    if count == 0:
        return "No se encontraron resultados."
    if count == 1:
        first = filtered[0]
        parts = [f"{k}: {sanitize_text(v)}" for k, v in first.items() if v is not None]
        return "Resultado: " + " | ".join(parts)
    if count <= 5:
        lines = [
            f"{i+1}. " + " | ".join(
                sanitize_text(str(r.get(c, ""))) for c in cols[:3]
            )
            for i, r in enumerate(filtered)
        ]
        return f"Se encontraron {count} resultados:\n" + "\n".join(lines)

    lines = [
        f"{i+1}. " + " | ".join(
            sanitize_text(str(r.get(c, ""))) for c in cols[:3]
        )
        for i, r in enumerate(filtered[:5])
    ]
    return f"Se encontraron {count} resultados. Los primeros:\n" + "\n".join(lines)
