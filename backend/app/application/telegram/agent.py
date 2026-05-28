"""Conversational agent — translates natural language to system commands.

Architecture:
  1. IntentClassifier (LLM) classifies user intent
  2. Route to SemanticLayer, DoctorQuery, CalendarQuery, or IntentRouter
  3. QueryExecutor fallback for unregistered questions (slow path)
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from backend.app.application.telegram.intent_classifier import (
    ClassifiedIntent,
    IntentClassifier,
)
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import LLMProvider
from backend.app.application.telegram.memory import MemoryManager, SessionState, SessionStore
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.sanitize import format_rows as shared_format_rows
from backend.app.application.telegram.semantic_layer import SemanticLayerResolver
from backend.app.application.telegram.types import AgentResult

logger = logging.getLogger(__name__)

_FOLLOWUP_PATTERNS = [
    re.compile(
        r"\b(y|son|ellos|ellas|eso|esa|esos|esas|mismo|misma|"
        r"exp[oó]rtalo|exportalo|esportalo)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(femenin[oa]s?|feminios?|femenios?|masculin[oa]s?|pdf|excel|listado|lista)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d+\s+o\s+\d+\b", re.IGNORECASE),
]


_FILTER_DIMS = {
    "rank_id",
    "rank_name",
    "rank",
    "sex",
    "area_id",
    "doctor_id",
    "date",
    "start",
    "department_id",
    "department_name",
    "department",
}

_FILTER_DIM_ALIASES = {
    "rank_id": "rank",
    "rank_name": "rank",
    "department_id": "department",
    "department_name": "department",
}

_MONTH_NAME_TO_NUMBER = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

def _looks_like_followup(text: str) -> bool:
    """Return True for short contextual follow-up requests."""
    return any(pattern.search(text) for pattern in _FOLLOWUP_PATTERNS)


def _extract_month_year(text: str) -> tuple[int, int] | None:
    """Extract a Spanish month and optional year from user text."""
    normalized = text.lower()
    month = None
    for name, number in _MONTH_NAME_TO_NUMBER.items():
        if re.search(rf"\b{name}\b", normalized):
            month = number
            break
    if month is None:
        numeric = re.search(r"\b(?:mes\s+)?(1[0-2]|0?[1-9])(?:/|-)(20\d{2})\b", normalized)
        if numeric:
            return int(numeric.group(1)), int(numeric.group(2))
        return None

    year_match = re.search(r"\b(20\d{2})\b", normalized)
    year = int(year_match.group(1)) if year_match else datetime.now().year
    return month, year


def _count_filter_dims(entity_hints: str) -> int:
    """Count how many filter dimensions are present in entity hints."""
    if not entity_hints:
        return 0
    parts = entity_hints.split(", ")
    dims_seen = set()
    for p in parts:
        key = p.split("=", 1)[0]
        if key in _FILTER_DIMS:
            dims_seen.add(_FILTER_DIM_ALIASES.get(key, key))
    return len(dims_seen)



def _format_rows(rows: list[dict], columns: list[str]) -> str:
    """Generate a human-readable response from query results."""
    return shared_format_rows(rows, columns)


class ConversationalAgent:
    """LLM-powered conversational agent for the Telegram bot."""

    def __init__(
        self,
        llm: LLMProvider,
        router: IntentRouter,
        query_executor: QueryExecutor | None = None,
        memory: MemoryManager | None = None,
        session_store: SessionStore | None = None,
        entity_resolver = None,
        doctor_query_service = None,
        session = None,
        calendar_query_service = None,
        semantic_layer_resolver: SemanticLayerResolver | None = None,
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        self._llm = llm
        self._router = router
        self._query_executor = query_executor
        self._memory = memory
        self._session_store = session_store
        self._entity_resolver = entity_resolver
        self._doctor_query_service = doctor_query_service
        self._session = session
        self._calendar_query_service = calendar_query_service
        self._semantic_layer_resolver = semantic_layer_resolver
        self._intent_classifier = intent_classifier

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def _classify_intent(
        self,
        text: str,
        entity_hints: str = "",
        resolved_entities: dict | None = None,
    ) -> ClassifiedIntent:
        """Classify user intent via LLM, with fallback for when LLM is unavailable."""
        if self._intent_classifier is not None:
            try:
                return self._intent_classifier.classify(
                    text,
                    entity_hints=entity_hints,
                    resolved_entities=resolved_entities,
                )
            except Exception:
                logger.warning("IntentClassifier failed", exc_info=True)

        # Fallback: basic keyword-based classification (for tests without LLM)
        text_lower = text.lower()
        if any(w in text_lower for w in ("cuantos", "cuántos", "total", "conteo")):
            if any(w in text_lower for w in ("medico", "doctor", "personal")):
                return ClassifiedIntent(domain="medicos", action="query", metric="total_doctors")
        if any(w in text_lower for w in ("hola", "buenos dias", "buenas tardes", "gracias")):
            return ClassifiedIntent(
                domain="general",
                action="reply",
                response_text="¡Hola! Soy el asistente de turnos medicos. ¿En que puedo ayudarte?",
            )
        return ClassifiedIntent(domain="general", action="ambiguous", confidence=0.3)

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    @staticmethod

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_via_router(
        self,
        action: str,
        query_type: str,
        params: dict,
        user_text: str,
        format: str | None = None,
    ) -> AgentResult | None:
        """Try IntentRouter. Returns None if query_type is unknown or execution fails."""
        entry = self._router.registry.get(query_type)
        if entry is None:
            return None
        try:
            result = self._router.handle(
                action=action,
                query_type=query_type,
                params=params,
                user_message=user_text,
                format=format,
            )
            # Router returns "not found" when query_type missing or SQL fails.
            # Treat this as a fallback trigger so query_executor gets a chance.
            if result.response_text.startswith(
                "No pude encontrar"
            ) or result.response_text.startswith("No se encontraron resultados"):
                return None
            return result
        except Exception:
            return None

    def _fallback_to_query_db(self, user_text: str, entity_hints: str = "") -> AgentResult:
        """Fallback: use QueryExecutor for NL-to-SQL."""
        if self._query_executor is None:
            return AgentResult(
                response_text="No pude encontrar informacion sobre eso en el sistema."
            )

        start = time.perf_counter()
        result = self._query_executor.execute(user_text, user_text, entity_hints=entity_hints)
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        if not result.get("ok"):
            logger.warning(
                "NL-to-SQL fallback failed",
                extra={
                    "telegram_event": "query_db_failed",
                    "match_type": "fallback",
                    "latency_ms": elapsed_ms,
                    "error": result.get("error"),
                },
            )
            return AgentResult(
                response_text="No pude encontrar informacion sobre eso en el sistema.",
                agent_action="query_db",
                tool_result=result,
            )

        data = result["data"]
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        if rows:
            response = self._format_nl_response(user_text, rows, columns)
        else:
            response = self._format_nl_empty_response(user_text)

        logger.info(
            "NL-to-SQL fallback completed",
            extra={
                "telegram_event": "query_db_completed",
                "match_type": "fallback",
                "latency_ms": elapsed_ms,
                "row_count": len(rows),
                "columns": columns,
                "truncated": data.get("truncated", False),
            },
        )
        return AgentResult(
            response_text=response,
            agent_action="query_db",
            tool_result=result,
        )

    # ------------------------------------------------------------------
    # NL response formatting
    # ------------------------------------------------------------------

    def _format_nl_response(
        self, original_question: str, rows: list[dict], columns: list[str]
    ) -> str:
        """Use LLM to format SQL results into natural Spanish text."""
        if len(rows) <= 20:
            try:
                formatted = self._llm.chat_complete(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Eres un asistente que convierte resultados de base de datos "
                                "en texto natural en espanol. Responde de forma conversacional "
                                "y clara. Incluye los datos relevantes. "
                                "NO inventes informacion que no este en los resultados."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Pregunta original: {original_question}\n\n"
                                f"Columnas: {', '.join(columns)}\n"
                                f"Resultados ({len(rows)} filas):\n"
                                f"{json.dumps(rows, default=str, ensure_ascii=False)}\n\n"
                                f"Responde en espanol de forma natural y conversacional."
                            ),
                        },
                    ],
                    temperature=0.3,
                )
                if formatted and len(formatted.strip()) > 20:
                    return formatted.strip()
            except Exception:
                logger.warning("NL response formatting failed, falling back to format_rows")

        return _format_rows(rows, columns)

    def _format_nl_empty_response(self, original_question: str) -> str:
        """Generate a natural language explanation when no data matches."""
        try:
            response = self._llm.chat_complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Eres un asistente de un sistema de turnos medicos. "
                            "El usuario hizo una consulta pero no se encontraron datos. "
                            "Responde de forma natural y amable en espanol, explicando "
                            "que no hay datos que coincidan. NO inventes datos. "
                            "Sugiere que intente con otros criterios si es apropiado."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"El usuario pregunto: '{original_question}'\n"
                            f"La base de datos no devolvio resultados.\n"
                            f"Genera una respuesta natural en espanol."
                        ),
                    },
                ],
                temperature=0.3,
            )
            if response and len(response.strip()) > 10:
                return response.strip()
        except Exception:
            logger.warning("NL empty response formatting failed")

        return "No se encontraron datos que coincidan con tu consulta en el sistema."

    def _remember_result(
        self,
        telegram_user_id: str | None,
        result: AgentResult,
        *,
        query_type: str | None = None,
        params: dict | None = None,
    ) -> None:
        """Store compact operational context for future follow-up messages."""
        if self._session_store is None or telegram_user_id is None:
            return
        if result.agent_action not in {"query", "export", "query_db"}:
            return

        tool_result = result.tool_result or {}
        data = tool_result.get("data") if isinstance(tool_result, dict) else None
        rows = data.get("rows", []) if isinstance(data, dict) else []
        filters = None
        if result.tool_entities:
            filters = result.tool_entities.get("applied_filters") or result.tool_entities.get(
                "requested_filters"
            )
        if filters is None:
            filters = self._filters_from_query_context(query_type, params or {})

        last_total = None
        if len(rows) == 1 and isinstance(rows[0], dict) and "total" in rows[0]:
            try:
                last_total = int(rows[0]["total"])
            except (TypeError, ValueError):
                last_total = None

        document_format = None
        if result.document_filename:
            document_format = result.document_filename.rsplit(".", 1)[-1].lower()

        domain = None
        period = None
        subject = None
        if result.tool_name == "calendar_query_service" and result.tool_entities:
            query_type = query_type or result.tool_entities.get("query_type")
            period = result.tool_entities.get("period")
            domain = "calendar_assignments"
            subject = (
                "assigned_doctors"
                if query_type in {
                    "count_assigned_doctors_by_month",
                    "list_calendar_assignments_by_date_range",
                }
                else None
            )
        if query_type in {
            "count_assigned_doctors_by_month",
            "list_assigned_doctors_by_month",
            "unassigned_doctors_by_month",
        }:
            domain = "calendar_assignments"
            period = period or {
                "year": params.get("year"),
                "month": params.get("month"),
            }
            subject = (
                "unassigned_doctors"
                if query_type == "unassigned_doctors_by_month"
                else "assigned_doctors"
            )
        elif query_type and ("doctor" in query_type or query_type.startswith("count_by_")):
            domain = "doctors"
        elif query_type == "mission_ranking":
            domain = "mission_ranking"
            period = {
                "year": params.get("year"),
                "month": params.get("month"),
            }
            subject = "mission_ranking"
        elif query_type == "list_active_missions":
            domain = "missions"
            subject = "active_missions"

        state = SessionState(
            last_query_type=query_type,
            last_params=params or {},
            last_results=rows[:50],
            last_filters=filters,
            last_tool_name=result.tool_name,
            last_agent_action=result.agent_action,
            last_operation=(result.tool_entities or {}).get("operation"),
            last_domain=domain,
            last_period=period,
            last_subject=subject,
            last_total=last_total,
            last_document_format=document_format,
        )
        self._session_store.set(telegram_user_id, state)


    def _mission_contextual_followup_result(
        self,
        text: str,
        telegram_user_id: str | None,
    ) -> AgentResult | None:
        """Answer follow-ups over the last active-missions listing."""
        if self._session_store is None or telegram_user_id is None:
            return None
        try:
            state = self._session_store.get(telegram_user_id)
        except Exception:
            logger.warning("Failed to load Telegram session state", exc_info=True)
            return None
        if (
            state is None
            or state.last_domain != "missions"
            or state.last_query_type != "list_active_missions"
            or not state.last_results
        ):
            return None

        normalized = text.lower()
        rows = [row for row in state.last_results if isinstance(row, dict)]
        if not rows:
            return None

        if re.search(r"\b(aprobadas?|confirmadas?)\b", normalized, re.IGNORECASE):
            filtered = [
                row
                for row in rows
                if str(row.get("estado", "")).lower() in {"confirmada", "confirmado"}
            ]
            columns = list(filtered[0].keys()) if filtered else list(rows[0].keys())
            response_text = (
                _format_rows(filtered, columns)
                if filtered
                else "No se encontraron misiones aprobadas en el listado anterior."
            )
            return AgentResult(
                response_text=response_text,
                agent_action="query",
                tool_name="mission_context",
                tool_entities={
                    "operation": "contextual_filter",
                    "query_type": "list_active_missions",
                    "filter": "confirmed",
                },
                tool_result={
                    "ok": True,
                    "source": "session_context",
                    "query_type": "list_active_missions",
                    "row_count": len(filtered),
                    "data": {"columns": columns, "rows": filtered},
                },
            )

        asks_responsibles = re.search(
            r"\b(responsables?|participantes?|medicos?|m[eé]dicos?)\b",
            normalized,
            re.IGNORECASE,
        )
        number_match = re.search(r"\b(?:numero|n[uú]mero|#)\s*(\d+)\b", normalized)
        if not (asks_responsibles and number_match):
            return None

        index = int(number_match.group(1)) - 1
        if index < 0 or index >= len(rows):
            return AgentResult(
                response_text="No encuentro ese numero en el listado anterior de misiones.",
                agent_action="ambiguous",
            )

        selected = rows[index]
        mission_keys = ("fecha_mision", "estado", "lugar", "descripcion")
        matching = [
            row
            for row in rows
            if all(row.get(key) == selected.get(key) for key in mission_keys)
        ]
        doctors = [
            {"medico": row.get("medico")}
            for row in matching
            if row.get("medico") and row.get("medico") != "Sin participante asignado"
        ]
        columns = ["medico"]
        response_text = (
            _format_rows(doctors, columns)
            if doctors
            else "Esa mision no tiene participantes asignados en el listado anterior."
        )
        return AgentResult(
            response_text=response_text,
            agent_action="query",
            tool_name="mission_context",
            tool_entities={
                "operation": "contextual_selection",
                "query_type": "list_active_missions",
                "selected_number": index + 1,
            },
            tool_result={
                "ok": True,
                "source": "session_context",
                "query_type": "list_active_missions",
                "row_count": len(doctors),
                "data": {"columns": columns, "rows": doctors},
            },
        )


    def _filters_from_query_context(
        self,
        query_type: str | None,
        params: dict,
    ) -> dict[str, Any] | None:
        """Infer reusable doctor filters from registry query metadata."""
        filters: dict[str, Any] = {}
        if query_type in {"count_by_specific_rank", "doctors_by_rank"} and params.get("rank"):
            filters["rank"] = params["rank"]
        if query_type in {"count_by_specific_sex", "doctors_by_sex"} and params.get("sex"):
            filters["sex"] = [params["sex"]]
        return filters or None

    def _resolved_from_filters(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Convert stored operational filters to EntityResolver-style data."""
        resolved: dict[str, Any] = {}
        if filters.get("rank"):
            resolved["rank"] = {
                "name": str(filters["rank"]).title(),
                "normalized_name": filters["rank"],
            }
        if filters.get("department"):
            resolved["department"] = {
                "name": str(filters["department"]).title(),
                "normalized_name": filters["department"],
            }
        if filters.get("sex"):
            resolved["sex"] = filters["sex"]
        return resolved

    def _merge_followup_context(
        self,
        telegram_user_id: str | None,
        resolved_entities: dict,
        entity_hints: str,
        user_text: str,
    ) -> tuple[dict, str, bool, str | None]:
        """Add missing filters from the user's last operational query."""
        if self._session_store is None or telegram_user_id is None:
            return resolved_entities, entity_hints, False, None
        if _count_filter_dims(entity_hints) >= 2:
            return resolved_entities, entity_hints, False, None
        if not _looks_like_followup(user_text):
            return resolved_entities, entity_hints, False, None

        state = self._session_store.get(telegram_user_id)
        if state is None or not state.last_filters:
            return resolved_entities, entity_hints, False, None

        merged = self._resolved_from_filters(state.last_filters)
        merged.update(resolved_entities)

        hints_parts = [part for part in entity_hints.split(", ") if part]
        if "rank" in merged and "rank_id" not in entity_hints and "rank='" not in entity_hints:
            hints_parts.append(f"rank='{merged['rank']['normalized_name']}'")
        if (
            "department" in merged
            and "department_id" not in entity_hints
            and "department='" not in entity_hints
        ):
            hints_parts.append(f"department='{merged['department']['normalized_name']}'")
        if "sex" in merged and "sex=" not in entity_hints:
            sex = merged["sex"]
            if isinstance(sex, list):
                hints_parts.append(f"sex='{'|'.join(sex)}'")
            else:
                hints_parts.append(f"sex='{sex}'")

        return merged, ", ".join(hints_parts), True, state.last_operation

    # ------------------------------------------------------------------
    # Backward-compat handler for old-format LLM responses
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(
        self,
        text: str,
        telegram_user_id: str | None = None,
        user_info: dict | None = None,
        actor_id: str | None = None,
    ) -> AgentResult:
        """
        Process a user message and return an AgentResult.

        1. Loads conversation history (if memory available)
        2. Calls LLM to translate message to command JSON
        3. Routes: router (fast), query_executor (fallback), reply, or ToolGateway (legacy)
        4. Returns final response
        """
        start = time.perf_counter()
        # 1. Load history
        history: list[dict] = []
        if self._memory and telegram_user_id:
            try:
                history = self._memory.load_history(telegram_user_id)
            except Exception:
                logger.warning("Failed to load history for %s", telegram_user_id, exc_info=True)
                history = []

        # 2. Pre-process entities
        entity_hints = ""
        resolved_entities: dict = {}
        ambiguous_entities: list[dict] = []
        if self._entity_resolver is not None:
            try:
                pre = self._entity_resolver.pre_process(text)
                entity_hints = pre.get("hints", "")
                resolved_entities = pre.get("resolved", {})
                ambiguous_entities = pre.get("ambiguous", [])
                if entity_hints or ambiguous_entities:
                    logger.info(
                        "Telegram entities pre-processed",
                        extra={
                            "telegram_event": "entities_preprocessed",
                            "entity_hints": entity_hints,
                            "ambiguous_count": len(ambiguous_entities),
                        },
                    )
            except Exception:
                logger.warning("EntityResolver.pre_process failed", exc_info=True)

        (
            resolved_entities,
            entity_hints,
            context_applied,
            followup_operation,
        ) = self._merge_followup_context(
            telegram_user_id,
            resolved_entities,
            entity_hints,
            text,
        )
        if context_applied:
            logger.info(
                "Telegram follow-up context applied",
                extra={
                    "telegram_event": "followup_context_applied",
                    "entity_hints": entity_hints,
                    "filter_dim_count": _count_filter_dims(entity_hints),
                },
            )

        session_state: SessionState | None = None
        if self._session_store is not None and telegram_user_id is not None:
            try:
                session_state = self._session_store.get(telegram_user_id)
            except Exception:
                logger.warning("Failed to load Telegram session state", exc_info=True)

        mission_followup = self._mission_contextual_followup_result(text, telegram_user_id)
        if mission_followup is not None:
            self._remember_result(
                telegram_user_id,
                mission_followup,
                query_type=(
                    mission_followup.tool_entities or {}
                ).get("query_type"),
                params={},
            )
            logger.info(
                "Agent resolved via mission contextual follow-up",
                extra={
                    "telegram_event": "agent_route_completed",
                    "match_type": "mission_contextual_followup",
                    "agent_action": mission_followup.agent_action,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                },
            )
            return mission_followup

        # ---- LLM-First Intent Classification ----
        classified = self._classify_intent(
            text=text,
            entity_hints=entity_hints,
            resolved_entities=resolved_entities,
        )
        logger.info(
            "Intent classified",
            extra={
                "telegram_event": "intent_classified",
                "domain": classified.domain,
                "action": classified.action,
                "metric": classified.metric,
                "query_type": classified.query_type,
                "confidence": classified.confidence,
            },
        )

        # ---- Route based on classified intent ----

        # Direct reply / ambiguous
        if classified.action in ("reply", "ambiguous"):
            return AgentResult(
                response_text=classified.response_text
                or "Necesito que me indiques que informacion del sistema quieres consultar.",
                agent_action=classified.action,
                tool_entities={"classified_intent": classified.__dict__},
            )

        # Semantic Layer metric route
        if classified.metric and self._semantic_layer_resolver is not None:
            try:
                entities_for_semantic = dict(resolved_entities)
                entities_for_semantic.update(classified.params)
                semantic_result = self._semantic_layer_resolver.resolve(
                    user_text=text,
                    domain=classified.domain,
                    action=classified.action,
                    entities=entities_for_semantic,
                    is_followup=False,
                    previous_metric=None,
                )
                if semantic_result is not None:
                    agent_result = self._semantic_layer_resolver.to_agent_result(
                        semantic_result,
                        user_text=text,
                        format=classified.format,
                    )
                    self._remember_result(
                        telegram_user_id,
                        agent_result,
                        query_type=f"semantic:{semantic_result.metric_name}",
                        params=classified.params,
                    )
                    logger.info(
                        "Agent resolved via semantic layer (LLM-classified)",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "semantic_layer",
                            "metric": semantic_result.metric_name,
                            "agent_action": agent_result.agent_action,
                            "latency_ms": round((time.perf_counter() - start) * 1000),
                        },
                    )
                    return agent_result
            except Exception:
                logger.warning("SemanticLayerResolver failed, falling through", exc_info=True)

        # Doctor query route
        if classified.domain == "medicos" and self._doctor_query_service is not None:
            try:
                result = self._doctor_query_service.execute(text, resolved_entities)
                if result is not None:
                    self._remember_result(telegram_user_id, result)
                    logger.info(
                        "Agent resolved via doctor query service (LLM-classified)",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "doctor_query_service",
                            "agent_action": result.agent_action,
                            "latency_ms": round((time.perf_counter() - start) * 1000),
                        },
                    )
                    return result
            except Exception:
                logger.warning("DoctorQueryService failed, falling through", exc_info=True)

        # Calendar query route
        if classified.domain == "calendario" and self._calendar_query_service is not None:
            try:
                result = self._calendar_query_service.execute(
                    classified.query_type or "list_calendar_assignments",
                    classified.params,
                )
                if result is not None:
                    self._remember_result(
                        telegram_user_id,
                        result,
                        query_type=classified.query_type or "list_calendar_assignments",
                        params=classified.params,
                    )
                    logger.info(
                        "Agent resolved via calendar query service (LLM-classified)",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "calendar_query_service",
                            "agent_action": result.agent_action,
                            "latency_ms": round((time.perf_counter() - start) * 1000),
                        },
                    )
                    return result
            except Exception:
                logger.warning("CalendarQueryService failed, falling through", exc_info=True)

        # IntentRouter route (query_type from classifier)
        if classified.query_type:
            router_result = self._route_via_router(
                classified.action if classified.action == "export" else "query",
                classified.query_type,
                classified.params,
                text,
                format=classified.format,
            )
            if router_result is not None:
                self._remember_result(
                    telegram_user_id,
                    router_result,
                    query_type=classified.query_type,
                    params=classified.params,
                )
                logger.info(
                    "Agent resolved via IntentRouter (LLM-classified)",
                    extra={
                        "telegram_event": "agent_route_completed",
                        "match_type": "intent_router",
                        "agent_action": router_result.agent_action,
                        "query_type": classified.query_type,
                        "latency_ms": round((time.perf_counter() - start) * 1000),
                    },
                )
                return router_result

        # Final fallback: QueryExecutor (NL-to-SQL) if entity hints >= 1
        if _count_filter_dims(entity_hints) >= 1 and self._query_executor is not None:
            logger.info("Falling back to QueryExecutor (LLM-classified)")
            result = self._fallback_to_query_db(text, entity_hints=entity_hints)
            self._remember_result(telegram_user_id, result)
            logger.info(
                "Agent resolved via QueryExecutor fallback",
                extra={
                    "telegram_event": "agent_route_completed",
                    "match_type": "query_executor_fallback",
                    "agent_action": result.agent_action,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                },
            )
            return result

        # Last resort: ask for clarification
        return AgentResult(
            response_text=(
                classified.response_text
                or "No estoy seguro de haber entendido. ¿Podrias ser mas especifico?"
            ),
            agent_action="ambiguous",
        )
