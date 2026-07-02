"""Shared SQL security validation used by QueryExecutor and SQLAgent.

Extracted from the original QueryExecutor so both the legacy fallback
and the new multi-turn SQL Agent enforce the exact same guard rails.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from backend.app.application.telegram.sanitize import _is_uuid_column
from backend.app.infrastructure.db.base import Base as _Base

_FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "EXEC", "EXECUTE", "CALL", "MERGE",
    "GRANT", "REVOKE", "LOCK", "UNLOCK",
    "INTO", "COPY", "PG_SLEEP", "PG_CANCEL_BACKEND",
]

_CTE_DML = re.compile(
    r"\bWITH\s+\w+\s+AS\s*\([^)]*\)\s*(DELETE|UPDATE|INSERT)",
    re.DOTALL | re.IGNORECASE,
)

_EXCLUDE_TABLES = {
    "alembic_version",
    "telegram_interactions",
    "telegram_user_links",
    "telegram_link_tokens",
    "audit_logs",
    "users",
}

_INTERNAL_IDENTIFIER_RE = re.compile(r"(^id$|_id$)", re.IGNORECASE)

_TABLE_DESCRIPTIONS = {
    "doctors": "Medicos del sistema. Datos personales y estado.",
    "doctor_allowed_areas": "Areas de servicio que cada medico puede cubrir.",
    "calendars": "Calendarios mensuales de turnos.",
    "calendar_versions": "Versiones de cada calendario.",
    "calendar_assignments": "Asignaciones de medicos a servicios en fechas.",
    "unresolved_gaps": "Huecos sin medico asignado en el calendario.",
    "doctor_availability": "Disponibilidad semanal/variable de medicos.",
    "doctor_restrictions": "Restricciones temporales de medicos.",
    "mission_assignments": "Misiones programadas.",
    "mission_participants": "Medicos asignados a cada mision.",
    "mission_candidate_rankings": "Rankings de candidatos para misiones por periodo.",
    "mission_candidate_ranking_entries": "Puntajes individuales del ranking.",
    "service_areas": "Areas de servicio (codigo y nombre visible).",
    "ranks": "Rangos/grados de los medicos.",
    "departments": "Departamentos de los medicos.",
    "deactivation_reasons": "Razones de baja de servicios.",
    "system_settings": "Configuraciones del sistema.",
    "users": "Usuarios del sistema (credenciales de acceso).",
    "notifications": "Historial de notificaciones enviadas.",
}


def build_schema_summary(session: Any | None = None) -> str:
    """Build a schema description string from SQLAlchemy metadata."""
    lines: list[str] = []

    for name in sorted(_Base.metadata.tables):
        if name in _EXCLUDE_TABLES:
            continue
        table = _Base.metadata.tables[name]
        desc = _TABLE_DESCRIPTIONS.get(name, "")
        to_append = []
        if desc:
            to_append.append(f"TABLE {name}: {desc}")
        else:
            to_append.append(f"TABLE {name}:")
        for col in table.columns:
            parts = [f"  - {col.name}: {col.type}"]
            if col.primary_key:
                parts.append(" PK")
            if not col.nullable:
                parts.append(" NOT NULL")
            if col.default is not None:
                parts.append(f" DEFAULT {col.default.arg}")
            for fk in col.foreign_keys:
                ref = fk.column
                parts.append(f" REFERENCES {ref.table.name}({ref.name})")
            to_append.append("".join(parts))
        lines.extend(to_append)
        lines.append("")

    if session is not None:
        try:
            from sqlalchemy import text as _sql_text

            _KNOWN_COLUMNS: dict[str, tuple[str, str]] = {
                "doctors.sex": ("doctors", "sex"),
                "doctors.availability_mode": ("doctors", "availability_mode"),
                "ranks.normalized_name": ("ranks", "normalized_name"),
            }
            lines.append("\n--- VALORES REALES DE COLUMNAS CRITICAS ---")
            for label, (tbl, col) in _KNOWN_COLUMNS.items():
                try:
                    result = session.execute(
                        _sql_text(
                            f'SELECT DISTINCT "{col}" FROM "{tbl}"'
                            f' WHERE "{col}" IS NOT NULL ORDER BY 1'
                        )
                    )
                    vals = [str(row[0]) for row in result.fetchall()]
                    if vals:
                        lines.append(f"{label} → {', '.join(vals)}")
                except Exception:
                    pass
            lines.append("--- FIN VALORES REALES ---\n")
        except Exception:
            pass

    return "\n".join(lines)


def validate_sql(sql: str) -> bool:
    """Return True if *sql* is a safe SELECT-only query."""
    if _CTE_DML.search(sql):
        return False

    cleaned = re.sub(r"'[^']*'", "", sql)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    cleaned = cleaned.strip().upper()

    if not cleaned.startswith("SELECT"):
        return False

    # Reject multiple statements (e.g. "SELECT … ; SELECT …")
    if re.search(r";\s*\S", cleaned):
        return False

    for kw in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", cleaned):
            return False
    for table_name in _EXCLUDE_TABLES:
        if re.search(rf"\b{re.escape(table_name.upper())}\b", cleaned):
            return False
    return True


def extract_sql_from_markdown(text: str) -> str:
    """Extract SQL from markdown code blocks if present."""
    text = text.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def execute_sql_safely(session: Any, sql: str) -> dict:
    """Execute validated SQL and return a standard result dict.

    Returns:
        {"ok": True, "data": {"columns": [...], "rows": [...], "row_count": N, "truncated": bool, "elapsed_seconds": float}}
        or {"ok": False, "error": "..."}
    """
    import logging
    import time

    logger = logging.getLogger(__name__)
    try:
        try:
            session.execute(text("SET LOCAL statement_timeout = '10000'"))
        except Exception:
            pass

        start = time.time()
        result = session.execute(text(sql))
        elapsed = time.time() - start

        rows = result.fetchmany(101)
        truncated = len(rows) > 100
        if truncated:
            rows = rows[:100]

        raw_columns = list(result.keys())
        raw_rows = [dict(zip(raw_columns, row, strict=False)) for row in rows]
        columns = [
            column
            for column in raw_columns
            if not _INTERNAL_IDENTIFIER_RE.search(column)
            and not _is_uuid_column(raw_rows, column)
        ]
        cleaned_rows = [
            {column: row.get(column) for column in columns} for row in raw_rows
        ]
        return {
            "ok": True,
            "data": {
                "columns": columns,
                "rows": cleaned_rows,
                "row_count": len(cleaned_rows),
                "truncated": truncated,
                "elapsed_seconds": round(elapsed, 2),
            },
        }
    except Exception as exc:
        logger.warning("Query SQL failed: %s | %s", sql[:120], exc)
        session.rollback()
        return {"ok": False, "error": f"Error en la consulta: {exc}"}
