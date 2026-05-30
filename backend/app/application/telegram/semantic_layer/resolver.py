"""SemanticLayerResolver — bridge between the ConversationalAgent and the engine.

The resolver tries to map a user's natural-language intent (already
pre-processed by EntityResolver) into a ``SemanticQuery``.  If the mapping
is confident enough, the query is executed deterministically via the engine.

If the intent does not map cleanly to the semantic layer, the resolver
returns ``None`` so the agent can fall back to the existing IntentRouter
or QueryExecutor.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .definitions import DIMENSIONS, METRICS
from .engine import SemanticLayerEngine
from .models import Filter, SemanticQuery, SemanticResult
from backend.app.application.telegram.sanitize import format_rows
from backend.app.application.telegram.types import AgentResult


class SemanticLayerResolver:
    """Maps interpreted user intents to SemanticQueries."""

    def __init__(self, session: Session) -> None:
        self.engine = SemanticLayerEngine(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def resolve(
        self,
        *,
        user_text: str,
        domain: str,
        action: str,
        entities: dict[str, Any],
        is_followup: bool = False,
        previous_metric: str | None = None,
    ) -> SemanticResult | None:
        """Try to resolve the user's intent into a SemanticQuery.

        Returns ``SemanticResult`` on success, ``None`` if the intent does
        not match any metric in the semantic layer.
        """
        sq = self._build_semantic_query(
            user_text=user_text,
            domain=domain,
            action=action,
            entities=entities,
            is_followup=is_followup,
            previous_metric=previous_metric,
        )
        if sq is None:
            return None
        return self.engine.execute(sq)

    _SUPPORTED_DOMAINS = {
        "medicos", "doctors", "personal",
        "calendario", "calendar", "servicios", "services",
        "misiones", "missions",
        "ranking", "ranking_misiones",
        "operativo", "resumen", "summary",
    }

    def is_semantic_query(self, domain: str, action: str, entities: dict[str, Any]) -> bool:
        """Quick check: does this intent look like something the semantic layer handles?"""
        return domain in self._SUPPORTED_DOMAINS

    # ------------------------------------------------------------------
    # Intent → SemanticQuery mapping
    # ------------------------------------------------------------------
    def _build_semantic_query(
        self,
        *,
        user_text: str,
        domain: str,
        action: str,
        entities: dict[str, Any],
        is_followup: bool = False,
        previous_metric: str | None = None,
    ) -> SemanticQuery | None:
        """Map domain/action/entities to a concrete SemanticQuery.

        This is the core routing logic.  It uses simple keyword matching
        and entity presence — no LLM calls here.
        """
        text_lower = user_text.lower()

        # --------------------------------------------------------------
        # Domain: doctors / medicos
        # --------------------------------------------------------------
        if domain in ("medicos", "doctors", "personal"):
            return self._resolve_doctor_query(text_lower, action, entities)

        # --------------------------------------------------------------
        # Domain: calendar / calendario / servicios
        # --------------------------------------------------------------
        if domain in ("calendario", "calendar", "servicios", "services"):
            return self._resolve_calendar_query(text_lower, action, entities)

        # --------------------------------------------------------------
        # Domain: missions / misiones
        # --------------------------------------------------------------
        if domain in ("misiones", "missions"):
            return self._resolve_mission_query(text_lower, action, entities)

        # --------------------------------------------------------------
        # Domain: ranking
        # --------------------------------------------------------------
        if domain in ("ranking", "ranking_misiones"):
            return self._resolve_ranking_query(text_lower, action, entities)

        # --------------------------------------------------------------
        # Domain: operativo / resumen
        # --------------------------------------------------------------
        if domain in ("operativo", "resumen", "summary"):
            return self._resolve_summary_query(text_lower, action, entities)

        return None

    # ------------------------------------------------------------------
    # Domain-specific resolvers
    # ------------------------------------------------------------------
    def _resolve_doctor_query(
        self, text_lower: str, action: str, entities: dict[str, Any]
    ) -> SemanticQuery | None:
        """Resolve doctor-related queries."""
        filters = self._extract_common_filters(entities)
        dims: list[str] = []

        # Count queries
        if any(w in text_lower for w in ("cuantos", "cuántos", "total", "conteo", "numero")):
            metric = "total_doctors"

            if "sexo" in entities or any(w in text_lower for w in ("sexo", "hombres", "mujeres", "masculino", "femenino")):
                metric = "doctors_by_sex"
            elif "rango" in entities or any(w in text_lower for w in ("rango", "rangos", "grado")):
                metric = "doctors_by_rank"
            elif "departamento" in entities or any(w in text_lower for w in ("departamento", "departamentos", "area")):
                metric = "doctors_by_department"

            return SemanticQuery(metric=metric, dimensions=dims, filters=filters)

        # Duplicate names
        if any(w in text_lower for w in ("duplicado", "repetido", "mismo nombre")):
            return SemanticQuery(metric="duplicate_doctor_names", filters=filters)

        # Last service
        if any(w in text_lower for w in ("ultimo servicio", "último servicio", "ultima vez", "última vez", "cuando fue")):
            return SemanticQuery(metric="last_service_by_doctor", dimensions=dims, filters=filters)

        # Service load / history
        if any(w in text_lower for w in ("historial", "servicios hechos", "cuantos servicios", "carga", "load")):
            return SemanticQuery(metric="doctor_service_load", dimensions=dims, filters=filters)

        # Unassigned
        if any(w in text_lower for w in ("sin asignar", "no asignado", "sin servicio", "ocioso")):
            return SemanticQuery(metric="unassigned_doctors", dimensions=dims, filters=filters)

        return None

    def _resolve_calendar_query(
        self, text_lower: str, action: str, entities: dict[str, Any]
    ) -> SemanticQuery | None:
        """Resolve calendar/service-related queries."""
        filters = self._extract_common_filters(entities)
        dims: list[str] = []

        # Calendar status
        if any(w in text_lower for w in ("estado del calendario", "calendario aprobado", "estado calendario")):
            return SemanticQuery(metric="calendar_status", filters=filters)

        # Total services
        if any(w in text_lower for w in ("total servicios", "cuantos servicios", "numero de servicios")):
            if "doctor" in entities:
                dims.append("doctor")
            return SemanticQuery(metric="total_services", dimensions=dims, filters=filters)

        # Assigned doctors count
        if any(w in text_lower for w in ("medicos asignados", "médicos asignados", "cuantos medicos", "distintos")):
            return SemanticQuery(metric="assigned_doctors_count", dimensions=dims, filters=filters)

        # Unresolved gaps
        if any(w in text_lower for w in ("hueco", "huecos", "sin cubrir", "falta asignar", "gap")):
            return SemanticQuery(metric="unresolved_gaps", dimensions=dims, filters=filters)

        # Pending confirmations
        if any(w in text_lower for w in ("pendiente", "confirmacion", "confirmaciones", "sin confirmar")):
            conf_type = "mission" if "mision" in text_lower else "service"
            filters.append(Filter(field="confirmation_type", operator="eq", value=conf_type))
            return SemanticQuery(metric="pending_confirmations", dimensions=dims, filters=filters)

        return None

    def _resolve_mission_query(
        self, text_lower: str, action: str, entities: dict[str, Any]
    ) -> SemanticQuery | None:
        """Resolve mission-related queries."""
        filters = self._extract_common_filters(entities)

        # Active missions
        if any(w in text_lower for w in ("activas", "proximas", "próximas", "programadas", "lista de misiones")):
            return SemanticQuery(metric="active_missions", filters=filters)

        # Pending confirmations
        if any(w in text_lower for w in ("pendiente", "confirmacion", "sin confirmar")):
            filters.append(Filter(field="confirmation_type", operator="eq", value="mission"))
            return SemanticQuery(metric="pending_confirmations", filters=filters)

        return None

    def _resolve_ranking_query(
        self, text_lower: str, action: str, entities: dict[str, Any]
    ) -> SemanticQuery | None:
        """Resolve ranking-related queries."""
        filters = self._extract_common_filters(entities)
        dims: list[str] = []

        if "rank" in entities:
            dims.append("rank")
        if "departamento" in entities:
            dims.append("department")

        return SemanticQuery(metric="mission_ranking", dimensions=dims, filters=filters)

    def _resolve_summary_query(
        self, text_lower: str, action: str, entities: dict[str, Any]
    ) -> SemanticQuery | None:
        """Resolve operational summary queries."""
        filters = self._extract_common_filters(entities)
        return SemanticQuery(metric="operational_summary", filters=filters)

    # ------------------------------------------------------------------
    # Result formatting
    # ------------------------------------------------------------------
    def to_agent_result(
        self,
        semantic_result: SemanticResult,
        user_text: str = "",
        format: str | None = None,
    ) -> AgentResult:
        """Convert a SemanticResult into an AgentResult ready for Telegram."""
        if not semantic_result.rows:
            return AgentResult(
                response_text="No se encontraron resultados.",
                agent_action="query",
                tool_entities={
                    "metric": semantic_result.metric_name,
                    "dimensions": semantic_result.dimensions,
                    "sql": semantic_result.sql,
                },
            )

        response_text = format_rows(semantic_result.rows, semantic_result.columns)
        if semantic_result.truncated:
            response_text += f"\n\n(Mostrando los primeros {len(semantic_result.rows)} de más resultados)"

        return AgentResult(
            response_text=response_text,
            agent_action="query",
            tool_entities={
                "metric": semantic_result.metric_name,
                "dimensions": semantic_result.dimensions,
                "sql": semantic_result.sql,
                "row_count": semantic_result.row_count,
                "truncated": semantic_result.truncated,
            },
            tool_result={
                "columns": semantic_result.columns,
                "rows": semantic_result.rows,
            },
        )

    # ------------------------------------------------------------------
    # Filter extraction helpers
    # ------------------------------------------------------------------
    def _extract_common_filters(self, entities: dict[str, Any]) -> list[Filter]:
        """Convert resolved entities into SemanticQuery filters."""
        filters: list[Filter] = []

        # Sex
        sex = entities.get("sexo") or entities.get("sex")
        if sex:
            filters.append(Filter(field="sex", operator="eq", value=sex))

        # Rank
        rank = entities.get("rango") or entities.get("rank")
        if rank:
            filters.append(Filter(field="rank", operator="eq", value=rank))

        # Department
        dept = entities.get("departamento") or entities.get("department")
        if dept:
            filters.append(Filter(field="department", operator="eq", value=dept))

        # Service area
        area = entities.get("area") or entities.get("service_area")
        if area:
            filters.append(Filter(field="service_area", operator="eq", value=area))

        # Date range
        start_date = entities.get("start_date")
        end_date = entities.get("end_date")
        if start_date and end_date:
            filters.append(Filter(field="date", operator="between", value=[start_date, end_date]))
        elif start_date:
            filters.append(Filter(field="date", operator="gte", value=start_date))
        elif end_date:
            filters.append(Filter(field="date", operator="lte", value=end_date))

        # Specific date
        specific_date = entities.get("date")
        if specific_date and not (start_date or end_date):
            filters.append(Filter(field="date", operator="eq", value=specific_date))

        # Month / Year
        month = entities.get("month")
        if month:
            filters.append(Filter(field="month", operator="eq", value=month))
        year = entities.get("year")
        if year:
            filters.append(Filter(field="year", operator="eq", value=year))

        # Doctor name
        doctor = entities.get("doctor") or entities.get("doctor_name")
        if doctor:
            filters.append(Filter(field="doctor", operator="like", value=doctor))

        # Status
        status = entities.get("status")
        if status:
            filters.append(Filter(field="status", operator="eq", value=status))

        # Top N
        top_n = entities.get("top_n") or entities.get("limit")
        if top_n and isinstance(top_n, int):
            filters.append(Filter(field="top_n", operator="eq", value=top_n))

        return filters
