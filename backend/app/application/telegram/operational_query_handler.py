"""OperationalQueryHandler — resolves operational queries through the safest path.

Tries each service in order:
  1. SemanticLayerResolver (deterministic metrics)
  2. DoctorQueryService (filtered doctor queries)
  3. CalendarQueryService (calendar/assignment queries)
  4. IntentRouter (predefined SQL queries)
  5. SQL Agent fallback (controlled text-to-SQL)

Logs match_type, used_sql, and fallback_reason for observability.
"""

from __future__ import annotations

import logging
import re
import time
from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from backend.app.application.telegram.entity_resolver import _MONTH_NAMES
from backend.app.application.telegram.types import AgentResult

logger = logging.getLogger(__name__)

_MONTH_RE = re.compile(
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
    r"octubre|noviembre|diciembre)"
)
_WEEK_RE = re.compile(r"(primera|segunda|tercera|cuarta|quinta)\s+semana")
_WEEK_ORDINALS = {"primera": 1, "segunda": 2, "tercera": 3, "cuarta": 4, "quinta": 5}
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


class OperationalResult:
    """Result from the operational query pipeline."""
    def __init__(
        self,
        *,
        ok: bool,
        match_type: str,
        response_text: str = "",
        agent_result: AgentResult | None = None,
        used_sql: bool = False,
        used_llm: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        self.ok = ok
        self.match_type = match_type
        self.response_text = response_text
        self.agent_result = agent_result
        self.used_sql = used_sql
        self.used_llm = used_llm
        self.fallback_reason = fallback_reason


class OperationalQueryHandler:
    """Resolves operational queries by trying services from safest to riskiest."""

    def __init__(
        self,
        semantic_layer: Any | None,
        doctor_service: Any | None,
        calendar_service: Any | None,
        intent_router: Any | None,
        sql_executor: Any | None,
        llm_provider: Any | None = None,
    ) -> None:
        self._semantic_layer = semantic_layer
        self._doctor_service = doctor_service
        self._calendar_service = calendar_service
        self._intent_router = intent_router
        self._sql_executor = sql_executor
        self._llm = llm_provider

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
        telegram_user_id: str = "",
    ) -> OperationalResult | None:
        """Run the full pipeline, return the first successful result."""
        start = time.perf_counter()

        # 1. Semantic layer (deterministic, no SQL except controlled templates)
        result = self.try_semantic_layer(
            user_text=user_text, domain=domain, action=action, entities=entities
        )
        if result is not None:
            return result

        # 2. Doctor query service — solo si el NLU dijo que la consulta es de
        #    médicos. Sin este gate respondía CUALQUIER pregunta: su filtro
        #    vacío ({}) nunca devuelve None, así que una consulta de calendario
        #    terminaba en la lista completa de médicos.
        if self._doctor_service and domain == "medicos":
            agent_result = self._doctor_service.execute(user_text, entities)
            if agent_result is not None and agent_result.response_text:
                return self._make_result(
                    agent_result, "doctor_service", used_sql=False
                )

        # 3. Calendar query service
        if self._calendar_service:
            query_type = self._detect_calendar_query(user_text, entities)
            if query_type:
                params = self._calendar_params_for(query_type, entities, user_text)
                if params is not None:
                    agent_result = self._calendar_service.execute(query_type, params)
                    if agent_result is not None and agent_result.response_text:
                        return self._make_result(
                            agent_result, "calendar_service", used_sql=False
                        )

        # 4. Intent router (predefined SQL templates)
        if self._intent_router:
            query_type = self._detect_router_query(user_text, entities)
            if query_type:
                router_result = self._intent_router.handle(
                    action="query",
                    query_type=query_type,
                    params=entities,
                )
                if router_result is not None and router_result.response_text:
                    return self._make_result(
                        router_result, "intent_router", used_sql=True
                    )

        # 5. SQL Agent fallback (last resort)
        if self._sql_executor:
            try:
                sql_result = self._sql_executor.execute(
                    nl_query=user_text,
                    user_text=user_text,
                    entity_hints=entities,
                )
                if sql_result and sql_result.get("ok"):
                    data = sql_result.get("data", {})
                    rows = data.get("rows", [])
                    response = self._format_sql_result(rows, data.get("columns", []))
                    return OperationalResult(
                        ok=True,
                        match_type="sql_fallback",
                        response_text=response,
                        used_sql=True,
                        fallback_reason=None,
                    )
                else:
                    logger.warning(
                        "SQL fallback failed",
                        extra={"error": sql_result.get("error", "unknown")},
                    )
                    return OperationalResult(
                        ok=False,
                        match_type="sql_fallback",
                        response_text="No se encontraron resultados.",
                        used_sql=True,
                        fallback_reason=sql_result.get("error"),
                    )
            except Exception as exc:
                logger.warning("SQL fallback exception", extra={"error": str(exc)})
                return OperationalResult(
                    ok=False,
                    match_type="sql_fallback",
                    response_text="No pude procesar esa consulta en este momento.",
                    used_sql=True,
                    fallback_reason=str(exc),
                )

        return None

    # ------------------------------------------------------------------
    # Individual path methods
    # ------------------------------------------------------------------

    def try_semantic_layer(
        self,
        *,
        user_text: str,
        domain: str,
        action: str,
        entities: dict[str, Any],
    ) -> OperationalResult | None:
        """Try to resolve via SemanticLayerResolver."""
        if not self._semantic_layer or not self._semantic_layer.is_semantic_query(
            domain, action, entities
        ):
            return None

        try:
            semantic_result = self._semantic_layer.resolve(
                user_text=user_text,
                domain=domain,
                action=action,
                entities=entities,
            )
            if semantic_result is None:
                return None

            agent_result = self._semantic_layer.to_agent_result(semantic_result)
            return OperationalResult(
                ok=True,
                match_type="semantic_layer",
                response_text=agent_result.response_text,
                agent_result=agent_result,
                used_sql=False,
                used_llm=False,
            )
        except Exception as exc:
            logger.warning("Semantic layer error", extra={"error": str(exc)})
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_calendar_query(
        self, text: str, entities: dict[str, Any] | None = None
    ) -> str | None:
        """Detect calendar-specific intents from user text.

        Sólo se devuelve un query_type cuyos datos de entrada existan de verdad.
        Antes, toda frase con «calendario» que no dijera «estado» caía en
        `list_calendar_assignments_by_date_range`, que indexa
        `params["start_date"]` sin defensa: «Hay calendario de junio 2026?» no
        trae rango de fechas, así que reventaba con KeyError y el usuario no
        recibía nada. Sin fechas el detector se abstiene — sustituir otra
        consulta sería contestar algo que nadie pidió — y el pipeline sigue.
        """
        text_lower = text.lower()
        fechas = entities or {}

        week_match = _WEEK_RE.search(text_lower)
        habla_de_calendario = (
            "calendario" in text_lower
            or week_match is not None
            or any(
                word in text_lower
                for word in ("hueco", "huecos", "sin cubrir", "cobertura")
            )
        )
        if not habla_de_calendario:
            return None

        if any(
            word in text_lower
            for word in (
                "estado", "status", "aprobad", "aprobacion", "pendiente",
                "hueco", "huecos", "sin cubrir", "cobertura",
                "hay calendario", "existe",
            )
        ):
            return "calendar_status"

        if fechas.get("start_date") and fechas.get("end_date"):
            return "list_calendar_assignments_by_date_range"

        if week_match:
            return "calendar_assignments"

        return None

    def _calendar_params_for(
        self, query_type: str, entities: dict[str, Any], user_text: str
    ) -> dict[str, Any] | None:
        """Deriva los params que CalendarQueryService espera para el query_type.

        Devuelve ``None`` cuando no se pueden derivar de verdad: el servicio
        indexa ``params["start_date"]`` sin defensa, así que mandarlo sin fechas
        es el KeyError que dejaba al usuario sin respuesta. Mejor abstenerse y
        dejar que el pipeline siga.
        """
        params = dict(entities)
        text_lower = user_text.lower()

        if params.get("month") is None:
            match = _MONTH_RE.search(text_lower)
            if match:
                params["month"] = _MONTH_NAMES[match.group(1)]
        if params.get("year") is None:
            match = _YEAR_RE.search(text_lower)
            if match:
                params["year"] = int(match.group(1))

        if query_type != "calendar_assignments":
            return params

        month = params.get("month")
        if month is None:
            return None
        year = int(params.get("year") or date.today().year)
        order = 1
        match = _WEEK_RE.search(text_lower)
        if match:
            order = _WEEK_ORDINALS[match.group(1)]
        # Un mes corto no tiene día 29: se ancla al último día real.
        last_day = monthrange(year, int(month))[1]
        start = date(year, int(month), min((order - 1) * 7 + 1, last_day))
        return {
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=6)).isoformat(),
        }

    def _detect_router_query(
        self, text: str, entities: dict[str, Any]
    ) -> str | None:
        """Detect intent from text for the router's predefined queries."""
        text_lower = text.lower()
        if "mision" in text_lower or "misiones" in text_lower:
            if "activa" in text_lower or "proxima" in text_lower or "lista" in text_lower:
                return "list_active_missions"
            if "confirmacion" in text_lower or "pendiente" in text_lower:
                return "pending_mission_confirmation"
            if "ranking" in text_lower:
                return "mission_ranking"
        if "summary" in text_lower or "resumen" in text_lower:
            return "operational_summary"
        return None

    def _format_sql_result(
        self, rows: list[dict], columns: list[str]
    ) -> str:
        """Format SQL result rows into readable Spanish text."""
        if not rows:
            return "No se encontraron resultados."
        if len(rows) == 1 and len(columns) <= 2:
            vals = [str(rows[0].get(c, "")) for c in columns]
            return "Resultado: " + ", ".join(vals)
        lines = [f"Se encontraron {len(rows)} resultados. Los primeros:"]
        for i, row in enumerate(rows[:5], 1):
            vals = [str(row.get(c, "")) for c in columns[:4]]
            lines.append(f"{i}. " + " | ".join(vals))
        if len(rows) > 5:
            lines.append(f"... y {len(rows) - 5} más.")
        return "\n".join(lines)

    def _make_result(
        self,
        agent_result: AgentResult,
        match_type: str,
        used_sql: bool = False,
    ) -> OperationalResult:
        return OperationalResult(
            ok=True,
            match_type=match_type,
            response_text=agent_result.response_text,
            agent_result=agent_result,
            used_sql=used_sql,
            used_llm=False,
        )
