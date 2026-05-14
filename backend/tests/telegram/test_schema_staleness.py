"""Tests that validate registry SQL templates stay in sync with the DB schema.

These tests prevent "schema staleness" — when a DB column is renamed or
a query type is added without updating the associated column title map or
export filename map.
"""
import re

from backend.app.application.telegram.intent_router import (
    _COLUMN_TITLE_MAP,
    _EXPORT_FILENAME_MAP,
    _column_title,
)
from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES

_SELECT_EXTRACTOR = re.compile(r"SELECT\s+(.*?)\s+FROM", re.DOTALL | re.IGNORECASE)
_ALIAS_EXTRACTOR = re.compile(r"\bAS\s+(\w+)", re.IGNORECASE)
_SUBQUERY_EXTRACTOR = re.compile(r"\(SELECT\s+.*?FROM\s+\w+", re.IGNORECASE)
_REPLY_DB_FIELDS = {"load_60d", "assignments_60d"}


def _sql_output_columns(sql: str) -> set[str]:
    """Extract the output column aliases from a SELECT SQL template."""
    match = _SELECT_EXTRACTOR.search(sql)
    if not match:
        return set()

    select_body = match.group(1)

    # Remove parenthesized subqueries before parsing columns
    # This handles operational_summary's (SELECT ...) AS alias
    simplified = re.sub(r"\([^()]*\)", "", select_body)
    # Also handle single-parent subqueries that the above misses
    while "(" in simplified and ")" in simplified:
        simplified = re.sub(r"\([^()]*\)", "", simplified)

    columns: set[str] = set()
    for part in select_body.split(","):
        part = part.strip()
        alias_match = _ALIAS_EXTRACTOR.search(part)
        if alias_match:
            columns.add(alias_match.group(1))
        else:
            # No explicit alias — extract the column name
            col = part.split(".")[-1].strip().strip('"')
            if "(" in col:
                # aggregate like COUNT(*) without alias → "count" or "total"
                columns.add(col)
            else:
                columns.add(col)
    return columns


# ---------------------------------------------------------------------------
# Validación: _COLUMN_TITLE_MAP cubre todas las columnas SQL
# ---------------------------------------------------------------------------


def test_all_query_columns_have_title_fallback() -> None:
    """Toda columna de output SQL tiene un título (aunque sea generado)."""
    seen_columns: set[str] = set()
    for qt in DEFAULT_QUERY_TYPES:
        cols = _sql_output_columns(qt["sql_template"])
        seen_columns.update(cols)

    for col in sorted(seen_columns):
        title = _column_title(col)
        assert title != "Columna" or col in _COLUMN_TITLE_MAP, (
            f"A columna '{col}' del query type '{qt['query_type']}' "
            f"no tiene entrada en _COLUMN_TITLE_MAP"
        )


# ---------------------------------------------------------------------------
# Validación: _EXPORT_FILENAME_MAP cubre todos los query types
# ---------------------------------------------------------------------------


def test_all_query_types_have_export_filename() -> None:
    """Cada query_type en DEFAULT_QUERY_TYPES tiene entrada en
    _EXPORT_FILENAME_MAP."""
    registered = {qt["query_type"] for qt in DEFAULT_QUERY_TYPES}
    mapped = set(_EXPORT_FILENAME_MAP.keys())

    missing = sorted(registered - mapped)
    assert not missing, (
        f"Query types sin entrada en _EXPORT_FILENAME_MAP: {missing}"
    )


# ---------------------------------------------------------------------------
# Validación: no hay entradas muertas en _EXPORT_FILENAME_MAP
# ---------------------------------------------------------------------------


def test_export_filename_map_has_no_dead_entries() -> None:
    """Toda entrada en _EXPORT_FILENAME_MAP tiene un query_type real."""
    registered = {qt["query_type"] for qt in DEFAULT_QUERY_TYPES}
    mapped = set(_EXPORT_FILENAME_MAP.keys())

    extra = sorted(mapped - registered)
    assert not extra, (
        f"Entradas en _EXPORT_FILENAME_MAP sin query_type correspondiente: {extra}"
    )
