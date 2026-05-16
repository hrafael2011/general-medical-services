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

from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES, QueryRegistry
from backend.app.application.telegram.sanitize import _is_uuid_column as _contains_uuid_values
from backend.app.application.telegram.sanitize import display_value, format_rows
from backend.app.application.telegram.types import AgentResult

# PDF generation (lazy-imported in _build_document to keep startup fast)

logger = logging.getLogger(__name__)

_DEFAULT_NOT_FOUND = "No pude encontrar información sobre eso en el sistema."
_DEFAULT_AMBIGUOUS = (
    "Necesito un poco más de detalle para ayudarte. "
    "¿Podrías ser más específico?"
)
_DEFAULT_EXPORT_OK = "Aquí tienes el reporte solicitado."


def _is_internal_identifier_column(column: str) -> bool:
    """Return True for technical identifier columns that should not be shown."""
    normalized = column.lower()
    return normalized == "id" or normalized.endswith("_id")


def _is_uuid_column(rows: list[dict], column: str) -> bool:
    """True when *column* contains only UUID values across all rows."""
    return _contains_uuid_values(rows, column)


def _public_columns(columns: list[str]) -> list[str]:
    """Columns safe to show to an operational user in Telegram/reports."""
    return [column for column in columns if not _is_internal_identifier_column(column)]


def _strip_internal_identifier_columns(
    rows: list[dict],
    columns: list[str],
) -> tuple[list[dict], list[str]]:
    public_columns = _public_columns(columns)
    # Also remove columns whose values are all UUIDs
    public_columns = [
        c for c in public_columns
        if not _is_uuid_column(rows, c)
    ]
    if public_columns == columns:
        return rows, columns
    return (
        [
            {column: row.get(column) for column in public_columns}
            for row in rows
        ],
        public_columns,
    )


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

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            rows, columns = _strip_internal_identifier_columns(rows, columns)
            tool_entities = {
                "query_type": query_type,
                "params": params,
                "operation": "query",
            }
            tool_result = {
                "ok": True,
                "source": "query_registry",
                "query_type": query_type,
                "row_count": len(rows),
                "data": {"columns": columns, "rows": rows},
            }
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para esa consulta.",
                    agent_action="query",
                    tool_name="query_registry",
                    tool_entities=tool_entities,
                    tool_result=tool_result,
                )
            return AgentResult(
                response_text=format_rows(rows, columns),
                agent_action="query",
                tool_name="query_registry",
                tool_entities=tool_entities,
                tool_result=tool_result,
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
        fmt = kwargs.get("format", "pdf")

        entry = self._registry.get(query_type) if query_type else None
        if entry is None:
            return AgentResult(response_text=_DEFAULT_NOT_FOUND)

        self._registry.increment_hit(query_type)

        try:
            rows, columns = self._execute_template(entry["sql_template"], params)
            rows, columns = _strip_internal_identifier_columns(rows, columns)
            tool_entities = {
                "query_type": query_type,
                "params": params,
                "operation": "export",
                "export_format": fmt or "pdf",
            }
            tool_result = {
                "ok": True,
                "source": "query_registry",
                "query_type": query_type,
                "row_count": len(rows),
                "data": {"columns": columns, "rows": rows},
            }
            if not rows:
                return AgentResult(
                    response_text="No se encontraron resultados para generar el reporte.",
                    agent_action="export",
                    tool_name="query_registry",
                    tool_entities=tool_entities,
                    tool_result=tool_result,
                )

            result = self._build_document(rows, columns, fmt, query_type)
            result.tool_name = "query_registry"
            result.tool_entities = tool_entities
            result.tool_result = tool_result
            return result
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

    def _execute_template(
        self,
        sql_template: str,
        params: dict[str, Any],
    ) -> tuple[list[dict], list[str]]:
        """Execute a parametrized SQL template and return (rows, columns)."""
        if self._session is None:
            logger.warning("No DB session set in IntentRouter")
            return [], []

        try:
            result = self._session.execute(sa_text(sql_template), params)
            columns = list(result.keys())
            rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
            return rows, columns
        except Exception as exc:
            logger.warning("SQL execution failed: %s | SQL: %s", exc, sql_template[:120])
            self._session.rollback()
            return [], []

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
    "total_services_by_month": "SERVICIOS_POR_MES.pdf",
    "count_assigned_doctors_by_month": "MEDICOS_ASIGNADOS_MES.pdf",
    "list_assigned_doctors_by_month": "MEDICOS_ASIGNADOS_MES.pdf",
    "unassigned_doctors_by_month": "MEDICOS_NO_ASIGNADOS_MES.pdf",
    "duplicate_doctor_names": "MEDICOS_DUPLICADOS.pdf",
    "calendar_approval_info": "AUDITORIA_CALENDARIO.pdf",
    "pending_mission_confirmation": "PENDIENTES_MISION.pdf",
    "pending_service_confirmation": "PENDIENTES_SERVICIO.pdf",
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
    "active_doctors": "Médicos Activos",
    "calendar_status": "Estado Calendario",
    "total_assignments": "Total Servicios",
    "unresolved_gaps": "Huecos",
    "description": "Descripción",
    "reason_code": "Motivo",
    "action_type": "Acción",
    "fecha": "Fecha",
    "fecha_mision": "Fecha Misión",
    "actor": "Actor",
    "medico": "Médico",
    "estado": "Estado",
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
    """Generate a real PDF document from query results using the institutional template."""
    from backend.app.application.reports.pdf_templates import generate_doctor_list_pdf

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
        "total_services_by_month": "TOTAL DE SERVICIOS POR MES",
        "count_assigned_doctors_by_month": "MÉDICOS ASIGNADOS POR MES",
        "list_assigned_doctors_by_month": "LISTADO DE MÉDICOS ASIGNADOS POR MES",
        "unassigned_doctors_by_month": "MÉDICOS NO ASIGNADOS POR MES",
        "duplicate_doctor_names": "MÉDICOS CON NOMBRES DUPLICADOS",
        "calendar_approval_info": "AUDITORÍA DE CAMBIOS DEL CALENDARIO",
        "pending_mission_confirmation": "CONFIRMACIONES PENDIENTES DE MISIÓN",
        "pending_service_confirmation": "CONFIRMACIONES PENDIENTES DE SERVICIO",
    }

    title = title_map.get(query_type, f"REPORTE - {query_type.upper()}")

    # Generic: use generate_doctor_list_pdf with SQL column titles
    header_titles = [_column_title(c) for c in columns]

    # Build data rows using column titles as keys (for mapping in the table)
    doctor_rows = []
    for row in rows:
        doctor_rows.append(
            {
                title: display_value(column, row.get(column, ""))
                for title, column in zip(header_titles, columns, strict=False)
            }
        )

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
        ws.append([display_value(c, row.get(c, "")) for c in columns])

    for i, col_title in enumerate(header):
        letter = openpyxl.utils.get_column_letter(i + 1)
        ws.column_dimensions[letter].width = max(12, len(col_title) + 4)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
