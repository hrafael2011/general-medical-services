"""
QueryExecutor — converts natural language questions to SQL and executes them.

Security: only SELECT statements are allowed. DML/DDL are blocked.
"""

import re
import time
from typing import Any

from sqlalchemy import text

# Import models so metadata knows all tables
import backend.app.infrastructure.db.models.audit  # noqa: F401
import backend.app.infrastructure.db.models.availability  # noqa: F401
import backend.app.infrastructure.db.models.calendars  # noqa: F401
import backend.app.infrastructure.db.models.catalogs  # noqa: F401
import backend.app.infrastructure.db.models.doctors  # noqa: F401
import backend.app.infrastructure.db.models.missions  # noqa: F401
import backend.app.infrastructure.db.models.notifications  # noqa: F401
import backend.app.infrastructure.db.models.telegram  # noqa: F401
import backend.app.infrastructure.db.models.user  # noqa: F401
from backend.app.infrastructure.db.base import Base as _Base

_FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "EXEC", "EXECUTE", "CALL", "MERGE",
    "GRANT", "REVOKE", "LOCK", "UNLOCK",
    "INTO", "COPY", "PG_SLEEP", "PG_CANCEL_BACKEND",
]

# Also block CTEs that start with WITH … DELETE/UPDATE/INSERT
_CTE_DML = re.compile(r"\bWITH\s+\w+\s+AS\s*\([^)]*\)\s*(DELETE|UPDATE|INSERT)", re.DOTALL | re.IGNORECASE)

_EXCLUDE_TABLES = {
    "alembic_version",
    "telegram_interactions",
    "telegram_user_links",
    "telegram_link_tokens",
    "audit_logs",
    "users",  # NEVER expose credentials table to LLM
}

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


def _is_internal_identifier_column(column: str) -> bool:
    normalized = column.lower()
    return normalized == "id" or normalized.endswith("_id")


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_uuid_column(rows: list[dict], column: str) -> bool:
    """True when *column* contains only UUID values across all rows."""
    if not rows:
        return False
    samples = [
        row.get(column) for row in rows[:5]
        if row.get(column) is not None
    ]
    if not samples:
        return False
    return all(
        isinstance(v, str) and bool(_UUID_RE.match(v))
        for v in samples
    )


def _strip_internal_identifier_columns(rows: list[dict], columns: list[str]) -> tuple[list[dict], list[str]]:
    public_columns = [
        column for column in columns
        if not _is_internal_identifier_column(column)
    ]
    # Also remove columns whose values are all UUIDs
    public_columns = [
        c for c in public_columns
        if not _is_uuid_column(rows, c)
    ]
    if public_columns == columns:
        return rows, columns
    return (
        [{column: row.get(column) for column in public_columns} for row in rows],
        public_columns,
    )


def _build_schema_summary(session: Any | None = None) -> str:
    """Build a schema description string from SQLAlchemy metadata.

    If *session* is provided, real DISTINCT values for critical columns
    are appended so the LLM generates correct SQL predicates.
    """
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

    # Append real column values so the LLM generates correct predicates.
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
                            f"SELECT DISTINCT \"{col}\" FROM \"{tbl}\""
                            f" WHERE \"{col}\" IS NOT NULL ORDER BY 1"
                        )
                    )
                    vals = [str(row[0]) for row in result.fetchall()]
                    if vals:
                        lines.append(
                            f"{label} → {', '.join(vals)}"
                        )
                except Exception:
                    pass  # best-effort
            lines.append("--- FIN VALORES REALES ---\n")
        except Exception:
            pass  # best-effort

    return "\n".join(lines)


class QueryExecutor:
    """Executes natural language database queries with LLM-generated SQL."""

    def __init__(self, session: Any, llm: Any) -> None:
        self._session = session
        self._llm = llm
        self._schema_summary = _build_schema_summary(session)

    def get_schema_summary(self) -> str:
        return self._schema_summary

    def execute(
        self,
        nl_query: str,
        user_text: str = "",
        entity_hints: str = "",
    ) -> dict:
        """
        Convert a natural language query to SQL, validate, execute, return results.

        Returns:
            {"ok": True, "data": {"columns": [...], "rows": [...], "row_count": N, ...}}
            or {"ok": False, "error": "..."}
        """
        sql = self._generate_sql(nl_query, user_text, entity_hints=entity_hints)
        if not sql:
            return {"ok": False, "error": "No se pudo generar una consulta SQL."}

        sql_clean = self._extract_sql(sql)
        if not sql_clean:
            return {"ok": False, "error": "No se pudo extraer SQL de la respuesta."}

        if not self._validate_sql(sql_clean):
            return {
                "ok": False,
                "error": "Solo se permiten consultas SELECT.",
                "sql": sql_clean,
                "source": "nl_to_sql",
            }

        result = self._run_sql(sql_clean)
        result["sql"] = sql_clean
        result["source"] = "nl_to_sql"
        if result.get("ok") and isinstance(result.get("data"), dict):
            result["row_count"] = result["data"].get("row_count", 0)
        return result

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from markdown code blocks if present."""
        text = text.strip()
        m = re.search(
            r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL
        )
        if m:
            return m.group(1).strip()
        # No code block — assume the whole response is SQL
        return text

    def _generate_sql(self, nl_query: str, user_text: str = "", entity_hints: str = "") -> str:
        """Send schema + query to LLM and extract SQL."""
        context = user_text or nl_query
        entity_section = ""
        if entity_hints:
            entity_section = (
                "ENTIDADES DETECTADAS (usa estos valores exactos en los predicados SQL):\n"
                f"{entity_hints}\n\n"
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres un generador de consultas SQL para PostgreSQL. "
                    "Genera unicamente SELECTs. Sin explicaciones."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Esquema de la base de datos:\n\n"
                    f"{self._schema_summary}\n\n"
                    f"{entity_section}"
                    f"Pregunta: {context}\n\n"
                    f"Genera una consulta SELECT de PostgreSQL para responder. "
                    f"Usa los nombres exactos de tablas y columnas. "
                    f"Incluye LIMIT 100. "
                    f"Usa alias en espanol con AS para las columnas. "
                    f"Responde SOLO con el SQL, sin explicaciones ni markdown."
                ),
            },
        ]
        return self._llm.chat_complete(messages, temperature=0.1)

    def _validate_sql(self, sql: str) -> bool:
        """Validate SQL is SELECT-only and contains no forbidden keywords."""
        # Block CTE-based DML: WITH … AS (…) DELETE/UPDATE/INSERT
        if _CTE_DML.search(sql):
            return False

        cleaned = re.sub(r"'[^']*'", "", sql)
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        cleaned = cleaned.strip().upper()

        if not cleaned.startswith("SELECT"):
            return False
        for kw in _FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", cleaned):
                return False
        for table in _EXCLUDE_TABLES:
            if re.search(rf"\b(?:FROM|JOIN)\s+\"?{re.escape(table.upper())}\"?\b", cleaned):
                return False
        return True

    def _run_sql(self, sql: str) -> dict:
        """Execute validated SQL and return results safely."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            # Set real PostgreSQL statement timeout (10 seconds)
            # Silently ignored by SQLite — only takes effect on PostgreSQL
            try:
                self._session.execute(text("SET LOCAL statement_timeout = '10000'"))
            except Exception:
                pass

            start = time.time()
            result = self._session.execute(text(sql))
            elapsed = time.time() - start

            rows = result.fetchmany(101)
            truncated = len(rows) > 100
            if truncated:
                rows = rows[:100]

            columns = list(result.keys())
            row_dicts = [dict(zip(columns, row)) for row in rows]
            row_dicts, columns = _strip_internal_identifier_columns(row_dicts, columns)
            return {
                "ok": True,
                "data": {
                    "columns": columns,
                    "rows": row_dicts,
                    "row_count": len(row_dicts),
                    "truncated": truncated,
                    "elapsed_seconds": round(elapsed, 2),
                },
            }
        except Exception as exc:
            logger.warning("Query SQL failed: %s | %s", sql[:120], exc)
            self._session.rollback()
            return {"ok": False, "error": f"Error en la consulta: {exc}"}
