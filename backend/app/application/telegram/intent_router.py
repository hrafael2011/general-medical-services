"""
IntentRouter — routes classified intents to execution.

Receives {action, query_type, params, format} from the agent's LLM call
and handles execution: direct reply, database query, report export, or clarification.
"""

import io
import logging
from typing import Any

from reportlab.lib.units import cm

from sqlalchemy import text as sa_text

from backend.app.application.telegram.types import AgentResult
from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES, QueryRegistry

# PDF generation (lazy-imported in _build_document to keep startup fast)

logger = logging.getLogger(__name__)

_DEFAULT_NOT_FOUND = "No pude encontrar información sobre eso en el sistema."
_DEFAULT_AMBIGUOUS = (
    "Necesito un poco más de detalle para ayudarte. "
    "¿Podrías ser más específico?"
)
_DEFAULT_EXPORT_OK = "Aquí tienes el reporte solicitado."


class IntentRouter:
    """Routes classified intents to query execution, export, or direct reply."""

    def __init__(self, registry: QueryRegistry | None = None) -> None:
        self._registry = registry or QueryRegistry()
        self._registry.register_many(DEFAULT_QUERY_TYPES)
        self._session: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def registry(self) -> QueryRegistry:
        return self._registry

    def set_session(self, session: Any) -> None:
        """Set the DB session for query execution."""
        self._session = session

    def handle(
        self,
        *,
        action: str,
        query_type: str | None,
        params: dict[str, Any] | None,
        user_message: str = "",
        response_text: str | None = None,
        format: str | None = None,  # noqa: A002
    ) -> AgentResult:
        """Route an intent to the appropriate handler.

        Args:
            action: 'reply', 'query', 'export', or 'ambiguous'.
            query_type: Name of the registered query type (for query/export).
            params: Parameters to fill the SQL template.
            user_message: The original user message.
            response_text: Pre-built response (for reply/ambiguous actions).
            format: Output format for export ('pdf', 'excel', 'json').

        Returns:
            AgentResult with response text and optional document.
        """
        handler = {
            "reply": self._handle_reply,
            "query": self._handle_query,
            "export": self._handle_export,
            "ambiguous": self._handle_ambiguous,
        }.get(action)

        if handler is None:
            logger.warning("Unknown action '%s' in IntentRouter", action)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        return handler(
            query_type=query_type,
            params=params or {},
            user_message=user_message,
            response_text=response_text,
            format=format,
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_reply(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Direct reply — no data needed."""
        text = kwargs.get("response_text") or _DEFAULT_NOT_FOUND
        return AgentResult(response_text=text)

    def _handle_ambiguous(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Ask for clarification, using LLM-provided text if available."""
        text = kwargs.get("response_text") or _DEFAULT_AMBIGUOUS
        return AgentResult(response_text=text)

    def _handle_query(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a query and return a natural-language response."""
        query_type = kwargs.get("query_type")
        params = kwargs.get("params") or {}
        user_message = kwargs.get("user_message", "")

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para esa consulta.",
                    agent_action="query",
                )
            return AgentResult(
                response_text=self._format_rows(rows, columns, user_message),
                agent_action="query",
            )
        except Exception as exc:
            logger.warning("Query '%s' failed: %s", query_type, exc)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

    def _handle_export(
        self,
        **kwargs: Any,
    ) -> AgentResult:
        """Execute a query and return results as a PDF/Excel document."""
        query_type = kwargs.get("query_type")
        params = kwargs.get("params") or {}
        user_message = kwargs.get("user_message", "")
        fmt = kwargs.get("format", "pdf")

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para generar el reporte.",
                    agent_action="export",
                )

            return self._build_document(rows, columns, fmt, query_type)
        except Exception as exc:
            logger.warning("Export '%s' failed: %s", query_type, exc)
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_document(
        self,
        rows: list[dict],
        columns: list[str],
        fmt: str,
        query_type: str,
    ) -> AgentResult:
        """Build a PDF/Excel document from query results."""
        if fmt in ("", None):
            fmt = "pdf"
        if fmt == "pdf":
            return _build_pdf_from_rows(rows, columns, query_type, fmt)
        if fmt == "excel":
            excel_bytes = _build_excel_from_rows(rows, columns, query_type)
            if excel_bytes:
                filename = query_type.replace("_", " ").title().replace(" ", "")[:30]
                return AgentResult(
                    response_text=f"{_DEFAULT_EXPORT_OK} ({len(rows)} registros, Excel).",
                    document_bytes=excel_bytes,
                    document_filename=f"{filename}.xlsx",
                    agent_action="export",
                )
        return AgentResult(
            response_text=f"{_DEFAULT_EXPORT_OK} ({len(rows)} registros, formato {fmt.upper()}).",
            agent_action="export",
        )

    def _execute_template(self, sql_template: str, params: dict[str, Any]) -> tuple[list[dict], list[str]]:
        """Execute a parametrized SQL template and return (rows, columns)."""
        if self._session is None:
            logger.warning("No DB session set in IntentRouter")
            return [], []

        try:
            result = self._session.execute(sa_text(sql_template), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows, columns
        except Exception as exc:
            logger.warning("SQL execution failed: %s | SQL: %s", exc, sql_template[:120])
            return [], []

    def _format_rows(self, rows: list[dict], columns: list[str], user_message: str) -> str:
        """Generate a natural-language response from query results."""
        count = len(rows)
        if count == 0:
            return "No se encontraron resultados."
        if count == 1:
            first = rows[0]
            parts = [f"{k}: {v}" for k, v in first.items() if v is not None]
            return "Resultado: " + " | ".join(parts)
        if count <= 5:
            lines = [f"{i+1}. " + " | ".join(
                str(r.get(c, "")) for c in columns[:3]
            ) for i, r in enumerate(rows)]
            return f"Se encontraron {count} resultados:\n" + "\n".join(lines)
        return f"Se encontraron {count} resultados. Los primeros:\n" + "\n".join(
            f"{i+1}. " + " | ".join(str(r.get(c, "")) for c in columns[:3])
            for i, r in enumerate(rows[:5])
        )

_EXPORT_FILENAME_MAP = {
    "list_active_doctors": "LISTADO_MEDICOS_ACTIVOS.pdf",
    "count_by_sex": "MEDICOS_POR_SEXO.pdf",
    "count_by_rank": "MEDICOS_POR_RANGO.pdf",
    "count_by_specific_rank": "MEDICOS_POR_RANGO.pdf",
    "doctors_by_sex": "MEDICOS_POR_SEXO.pdf",
    "doctors_by_rank": "MEDICOS_POR_RANGO.pdf",
    "doctor_detail": "DETALLE_MEDICO.pdf",
    "doctors_working_date": "MEDICOS_EN_FECHA.pdf",
    "calendar_status_month": "ESTADO_CALENDARIO.pdf",
    "assignment_count_by_date_range": "SERVICIOS_POR_MEDICO.pdf",
    "mission_ranking": "RANKING_MISIONES.pdf",
    "operational_summary": "RESUMEN_OPERATIVO.pdf",
    "doctors_pending_availability": "MEDICOS_SIN_DISPONIBILIDAD.pdf",
    "count_doctors_total": "TOTAL_MEDICOS.pdf",
    "doctor_history_60d": "HISTORIAL_MEDICO.pdf",
    "count_doctors_by_department": "MEDICOS_POR_DEPARTAMENTO.pdf",
    "count_by_specific_sex": "MEDICOS_POR_SEXO.pdf",
    "doctor_history_by_name": "HISTORIAL_MEDICO.pdf",
    "assignments_by_area": "SERVICIOS_POR_AREA.pdf",
    "unresolved_gaps_month": "HUECOS_POR_MES.pdf",
}

_COLUMN_TITLE_MAP: dict[str, str] = {
    "name": "Nombre",
    "sex": "Sexo",
    "rank": "Rango",
    "total": "Total",
    "count": "Cantidad",
    "display_name": "Área",
    "area": "Área",
    "service_date": "Fecha",
    "service_area_name": "Área",
    "doctor_name": "Médico",
    "assignment_source": "Fuente",
    "availability_mode": "Disponibilidad",
    "active": "Activo",
    "service_active": "Servicio",
    "search": "Búsqueda",
    "status": "Estado",
    "month": "Mes",
    "year": "Año",
    "start_date": "Fecha Inicio",
    "end_date": "Fecha Fin",
    "period_year": "Año",
    "period_month": "Mes",
    "ranking_position": "#",
    "total_load_score": "Carga",
    "eligible": "Elegible",
    "department": "Departamento",
    "doctor_id": "ID Médico",
    "id": "ID",
}

_DEFAULT_COLUMN_TITLE = "Columna"


def _column_title(col: str) -> str:
    """Map a SQL column name to a human-readable Spanish title."""
    return _COLUMN_TITLE_MAP.get(col, col.replace("_", " ").title())


def _build_pdf_from_rows(
    rows: list[dict],
    columns: list[str],
    query_type: str,
    fmt: str,
) -> AgentResult:
    """Generate a real PDF document from query results using the institutional template.

    Uses generate_doctor_list_pdf for generic tabular data.
    Specialised templates are used for known report types.
    """
    from backend.app.application.reports.pdf_templates import (
        generate_doctor_list_pdf,
        generate_mission_ranking_pdf,
        generate_operational_summary_pdf,
    )

    if not rows:
        return AgentResult(
            response_text="No se encontraron resultados para generar el reporte.",
            agent_action="export",
        )

    title_map = {
        "list_active_doctors": "LISTADO DE MÉDICOS ACTIVOS",
        "count_by_sex": "MÉDICOS POR SEXO",
        "count_by_rank": "MÉDICOS POR RANGO",
        "count_by_specific_rank": "MÉDICOS POR RANGO",
        "doctors_by_sex": "LISTADO DE MÉDICOS POR SEXO",
        "doctors_by_rank": "LISTADO DE MÉDICOS POR RANGO",
        "doctor_detail": "DETALLE DE MÉDICO",
        "doctors_working_date": "MÉDICOS EN SERVICIO POR FECHA",
        "calendar_status_month": "ESTADO DEL CALENDARIO",
        "assignment_count_by_date_range": "SERVICIOS POR MÉDICO",
        "mission_ranking": "RANKING DE CANDIDATOS PARA MISIONES",
        "operational_summary": "RESUMEN OPERATIVO",
        "doctors_pending_availability": "MÉDICOS SIN DISPONIBILIDAD",
        "count_doctors_total": "TOTAL DE MÉDICOS",
        "doctor_history_60d": "HISTORIAL DE SERVICIOS (60 DÍAS)",
        "count_doctors_by_department": "MÉDICOS POR DEPARTAMENTO",
        "count_by_specific_sex": "MÉDICOS POR SEXO",
        "doctor_history_by_name": "HISTORIAL DE SERVICIOS (60 DÍAS)",
        "assignments_by_area": "SERVICIOS POR ÁREA",
        "unresolved_gaps_month": "HUECOS SIN ASIGNAR POR MES",
    }

    title = title_map.get(query_type, f"REPORTE - {query_type.upper()}")

    # Special case: operational summary
    if query_type == "operational_summary":
        summary = {"period": {}, "active_doctors": 0, "calendar_status": "N/A",
                    "total_assignments": 0, "unresolved_gaps": 0}
        for row in rows:
            summary["active_doctors"] = row.get("active_doctors", 0)
            summary["calendar_status"] = row.get("calendar_status", "N/A")
            summary["total_assignments"] = row.get("total_assignments", 0)
            summary["unresolved_gaps"] = row.get("unresolved_gaps", 0)
        pdf_bytes = generate_operational_summary_pdf(summary)
        filename = _EXPORT_FILENAME_MAP.get(query_type, "REPORTE.pdf")
        return AgentResult(
            response_text=f"{_DEFAULT_EXPORT_OK} ({len(rows)} registros, PDF).",
            document_bytes=pdf_bytes,
            document_filename=filename,
            agent_action="export",
        )

    # Special case: mission ranking
    if query_type == "mission_ranking" and "ranking_position" in columns:
        entries = [
            {
                "position": r.get("ranking_position", i + 1),
                "doctor_name": r.get("doctor_name", r.get("name", "")),
                "total_load_score": r.get("total_load_score", 0),
                "eligible": r.get("eligible", False),
            }
            for i, r in enumerate(rows)
        ]
        pdf_bytes = generate_mission_ranking_pdf(entries, 1, 2026)
        filename = _EXPORT_FILENAME_MAP.get(query_type, "REPORTE.pdf")
        return AgentResult(
            response_text=f"{_DEFAULT_EXPORT_OK} ({len(entries)} registros, PDF).",
            document_bytes=pdf_bytes,
            document_filename=filename,
            agent_action="export",
        )

    # Generic: use generate_doctor_list_pdf with SQL column titles
    header_titles = [_column_title(c) for c in columns]

    # Build data rows using column titles as keys (for mapping in the table)
    doctor_rows = []
    for row in rows:
        doctor_rows.append({t: str(row.get(c, "")) for t, c in zip(header_titles, columns)})

    col_widths = [max(2.5 * cm, len(t) * 0.18 * cm) for t in header_titles]
    # Cap max width
    col_widths = [min(w, 6 * cm) for w in col_widths]

    pdf_bytes = generate_doctor_list_pdf(
        doctor_rows,
        title=title,
        columns=header_titles,
        col_widths=col_widths,
    )
    filename = _EXPORT_FILENAME_MAP.get(query_type, "REPORTE.pdf")

    return AgentResult(
        response_text=f"{_DEFAULT_EXPORT_OK} ({len(rows)} registros, PDF).",
        document_bytes=pdf_bytes,
        document_filename=filename,
        agent_action="export",
    )


def _build_excel_from_rows(
    rows: list[dict],
    columns: list[str],
    query_type: str,
) -> bytes | None:
    """Generate an Excel file from query results."""
    try:
        import openpyxl
    except ImportError:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte"

    header = [_column_title(c) for c in columns]
    ws.append(header)

    for row in rows:
        ws.append([str(row.get(c, "")) for c in columns])

    for i, _ in enumerate(header):
        ws.column_dimensions[chr(65 + i)].width = max(12, len(header[i]) + 4)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
