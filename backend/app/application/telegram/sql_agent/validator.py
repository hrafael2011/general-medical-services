"""SQLValidator — programmatic guardrails for generated SQL queries.

Validates SQL *before* execution to enforce security, correctness and
complexity boundaries.  This is the last line of defence; it complements
(but does not replace) the security checks in ``security.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.app.infrastructure.db.base import Base as _Base


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a SQL validation pass."""

    ok: bool
    rule: str = ""
    detail: str = ""


class SQLValidator:
    """Programmatic validator for LLM-generated SQL.

    Checks are ordered from cheapest to most expensive so we fail fast.
    """

    # ------------------------------------------------------------------
    # Rule sets
    # ------------------------------------------------------------------
    _FORBIDDEN_FUNCTIONS = {
        "pg_sleep", "pg_cancel_backend", "pg_terminate_backend",
        "lo_import", "lo_export", "lo_unlink",
        "pg_read_file", "pg_read_binary_file",
        "copy_from", "copy_to",
    }

    _DANGEROUS_PATTERNS = [
        # Multiple statements
        (re.compile(r";\s*(?!\s*$)"), "multiple_statements", "Solo una sentencia SQL permitida."),
        # Comment injection
        (re.compile(r"/\*.*?\*/", re.DOTALL), "block_comment", "Comentarios SQL no permitidos."),
        (re.compile(r"--.*"), "line_comment", "Comentarios SQL no permitidos."),
        # Union-based injection patterns
        (re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE), "union_injection", "UNION no permitido sin autorizacion."),
        # Stacked queries
        (re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|CALL)\b", re.IGNORECASE), "stacked_query", "Queries apiladas no permitidas."),
        # Into outfile / dumpfile
        (re.compile(r"\bINTO\s+(OUTFILE|DUMPFILE)\b", re.IGNORECASE), "file_write", "Escritura de archivos bloqueada."),
        # Load file
        (re.compile(r"\bLOAD\s+DATA\b", re.IGNORECASE), "file_read", "Lectura de archivos bloqueada."),
    ]

    def __init__(self, max_rows: int = 100, max_query_length: int = 2000) -> None:
        self._max_rows = max_rows
        self._max_query_length = max_query_length
        self._known_tables = set(_Base.metadata.tables.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def validate(self, sql: str) -> ValidationResult:
        """Run all validation rules and return the first failure, or ok=True."""
        checks = [
            self._check_length,
            self._check_no_dml,
            self._check_single_select,
            self._check_no_dangerous_patterns,
            self._check_no_forbidden_functions,
            self._check_tables_exist,
            self._check_no_excluded_tables,
            self._check_has_limit_or_aggregate,
        ]
        for check in checks:
            result = check(sql)
            if not result.ok:
                return result
        return ValidationResult(ok=True)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------
    def _check_length(self, sql: str) -> ValidationResult:
        if len(sql) > self._max_query_length:
            return ValidationResult(
                ok=False,
                rule="max_length",
                detail=f"Query demasiado largo ({len(sql)} > {self._max_query_length} chars).",
            )
        return ValidationResult(ok=True)

    def _check_single_select(self, sql: str) -> ValidationResult:
        """Ensure the query is a single SELECT statement."""
        stripped = sql.strip().upper()
        if not stripped.startswith("SELECT"):
            return ValidationResult(
                ok=False, rule="not_select", detail="Solo sentencias SELECT permitidas."
            )
        return ValidationResult(ok=True)

    def _check_no_dml(self, sql: str) -> ValidationResult:
        """Block INSERT, UPDATE, DELETE, DROP, etc."""
        cleaned = re.sub(r"'[^']*'", "", sql)
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        cleaned = cleaned.upper()
        forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
                     "CREATE", "REPLACE", "MERGE", "GRANT", "REVOKE", "LOCK"}
        for kw in forbidden:
            if re.search(rf"\b{kw}\b", cleaned):
                return ValidationResult(
                    ok=False, rule="dml_detected", detail=f"Palabra clave prohibida: {kw}"
                )
        return ValidationResult(ok=True)

    def _check_no_forbidden_functions(self, sql: str) -> ValidationResult:
        cleaned = sql.upper()
        for fn in self._FORBIDDEN_FUNCTIONS:
            if re.search(rf"\b{fn.upper()}\b", cleaned):
                return ValidationResult(
                    ok=False, rule="forbidden_function", detail=f"Funcion prohibida: {fn}"
                )
        return ValidationResult(ok=True)

    def _check_no_dangerous_patterns(self, sql: str) -> ValidationResult:
        for pattern, rule_name, detail in self._DANGEROUS_PATTERNS:
            if pattern.search(sql):
                return ValidationResult(ok=False, rule=rule_name, detail=detail)
        return ValidationResult(ok=True)

    def _check_tables_exist(self, sql: str) -> ValidationResult:
        """Verify every table referenced in the query exists in the schema."""
        # If metadata is empty (models not imported), skip this check
        if not self._known_tables:
            return ValidationResult(ok=True)
        # Extract table names from FROM and JOIN clauses
        # This is a heuristic, not a full SQL parser
        table_pattern = re.compile(
            r"\b(FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            re.IGNORECASE,
        )
        for match in table_pattern.finditer(sql):
            table_name = match.group(2).lower()
            if table_name not in self._known_tables:
                return ValidationResult(
                    ok=False,
                    rule="unknown_table",
                    detail=f"Tabla desconocida: {table_name}",
                )
        return ValidationResult(ok=True)

    def _check_no_excluded_tables(self, sql: str) -> ValidationResult:
        from backend.app.application.telegram.sql_agent.security import _EXCLUDE_TABLES
        cleaned = re.sub(r"'[^']*'", "", sql)
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        cleaned = cleaned.upper()
        for table in _EXCLUDE_TABLES:
            if re.search(rf"\b{re.escape(table.upper())}\b", cleaned):
                return ValidationResult(
                    ok=False,
                    rule="excluded_table",
                    detail=f"Tabla excluida: {table}",
                )
        return ValidationResult(ok=True)

    def _check_has_limit_or_aggregate(self, sql: str) -> ValidationResult:
        """Non-aggregate SELECTs should have a LIMIT to avoid massive result sets."""
        cleaned = sql.upper()
        has_aggregate = any(
            re.search(rf"\b{agg}\s*\(", cleaned)
            for agg in ("COUNT", "SUM", "AVG", "MIN", "MAX")
        )
        has_limit = re.search(r"\bLIMIT\s+\d+", cleaned) is not None
        if not has_aggregate and not has_limit:
            return ValidationResult(
                ok=False,
                rule="missing_limit",
                detail="Queries sin agregacion deben incluir LIMIT.",
            )
        return ValidationResult(ok=True)
