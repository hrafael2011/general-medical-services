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

from backend.app.application.telegram.input_sanitizer import InputSanitizer
from backend.app.application.telegram.intent_classifier import (
    ClassifiedIntent,
    IntentClassifier,
    NLUEngine,
    NLUResult,
)
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import LLMProvider
from backend.app.application.telegram.memory import MemoryManager, SessionState, SessionStore
from backend.app.application.telegram.nl_response import generate_response
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.sanitize import format_rows as shared_format_rows
from backend.app.application.telegram.semantic_layer import SemanticLayerResolver
from backend.app.application.telegram.tool_registry import ToolRegistry
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
        nlu_engine: NLUEngine | None = None,
        tool_registry: ToolRegistry | None = None,
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
        self._nlu_engine = nlu_engine
        self._tool_registry = tool_registry
        self._input_sanitizer = InputSanitizer()

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

        # Greetings
        if any(w in text_lower for w in ("hola", "buenos dias", "buenas tardes", "buenas noches", "gracias", "saludos")):
            return ClassifiedIntent(
                domain="general",
                action="reply",
                response_text="¡Hola! Soy el asistente de turnos medicos. ¿En que puedo ayudarte?",
            )

        # Calendar queries
        if any(w in text_lower for w in ("semana de", "primera semana", "segunda semana", "tercera semana", "cuarta semana")):
            if any(w in text_lower for w in ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")):
                return ClassifiedIntent(domain="calendario", action="query")
        if "calendario" in text_lower:
            return ClassifiedIntent(domain="calendario", action="query")

        # Export
        if any(w in text_lower for w in ("exporta", "exportar", "exportalo", "exportame", "esporta", "pdf", "excel", "xlsx")):
            return ClassifiedIntent(domain="medicos", action="export")

        # Mission ranking
        if "mision" in text_lower or "misiones" in text_lower:
            return ClassifiedIntent(domain="medicos", action="query", query_type="mission_ranking")

        # Doctor count / list queries
        if any(w in text_lower for w in ("cuantos", "cuántos", "cuantas", "cuántas", "total", "conteo", "lista", "listado", "listame", "dame", "muestrame", "mostrame")):
            if any(w in text_lower for w in ("medico", "medicos", "doctor", "doctores", "doctora", "personal", "cabo", "cabos", "sargento", "sargentos", "pasante", "pasantes", "contrata", "contratas")):
                return ClassifiedIntent(domain="medicos", action="query")

        # Generic doctor domain
        if any(w in text_lower for w in ("medico", "medicos", "doctor", "doctores", "doctora", "cabo", "cabos", "sargento", "sargentos", "pasante", "pasantes", "contrata", "contratas")):
            return ClassifiedIntent(domain="medicos", action="query")

        # Follow-ups with resolved medical entities but no obvious keywords
        if resolved_entities and any(k in resolved_entities for k in ("rank", "sex", "department")):
            return ClassifiedIntent(domain="medicos", action="query")

        return ClassifiedIntent(domain="general", action="ambiguous", confidence=0.3)

    # ------------------------------------------------------------------
    # JSON parsing
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
        user: Any | None = None,  # UserModel for permission checks
    ) -> AgentResult:
        """Process a user message through the LLM-first NLU pipeline.

        1. Load conversation history
        2. Single NLU call (entity extraction + tool selection + params)
        3. Tool dispatch → NL response generation
        """
        start = time.perf_counter()

        # Phase 1: Load conversation history
        history: list[dict] = []
        if self._memory and telegram_user_id:
            try:
                history = self._memory.load_history(telegram_user_id)
            except Exception:
                logger.warning("Failed to load history for %s", telegram_user_id, exc_info=True)

        # Phase 2: NLU — use new engine when available, fall back to legacy
        if self._nlu_engine is not None:
            return self._process_llm_first(text, telegram_user_id, history, start, user=user)

        # Legacy path: EntityResolver + IntentClassifier + if-elif chain
        return self._process_legacy(text, telegram_user_id, history, start)

    # ------------------------------------------------------------------
    # LLM-First pipeline (new)
    # ------------------------------------------------------------------

    def _process_llm_first(
        self,
        text: str,
        telegram_user_id: str | None,
        history: list[dict],
        start: float,
        user: Any | None = None,
    ) -> AgentResult:
        """New pipeline: single LLM call → tool dispatch → NL response."""
        # Sanitize input before reaching the LLM (defense in depth)
        is_safe, _ = self._input_sanitizer.sanitize(text)
        if not is_safe:
            logger.warning(
                "Prompt injection blocked in agent",
                extra={"telegram_user_id": telegram_user_id},
            )
            return AgentResult(response_text="⚠️ No puedo procesar esa solicitud.")

        # NLU: entity extraction + tool selection + params in one call
        nlu_result = self._nlu_engine.classify(
            text,
            conversation_history=history,
        )
        logger.info(
            "NLU classified",
            extra={
                "telegram_event": "nlu_classified",
                "tool": nlu_result.tool,
                "params": nlu_result.params,
                "confidence": nlu_result.confidence,
            },
        )

        # Clarification needed
        if nlu_result.needs_clarification:
            return AgentResult(
                response_text=nlu_result.clarification_question or (
                    "¿Podrías ser más específico? No entendí bien tu consulta."
                ),
                agent_action="ambiguous",
            )

        # Reply tool (greetings, help, etc.)
        if nlu_result.tool == "reply":
            return self._handle_reply(text, nlu_result)

        # Tool dispatch
        tool_result = self._dispatch_tool(nlu_result.tool, nlu_result.params, text, user=user)

        # Generate NL response
        response_text = self._generate_nl_response(text, nlu_result, tool_result, history)

        agent_result = AgentResult(
            response_text=response_text,
            agent_action="query",
            tool_name=nlu_result.tool,
            tool_entities={"tool": nlu_result.tool, "params": nlu_result.params},
            tool_result=tool_result,
        )

        self._remember_result(
            telegram_user_id,
            agent_result,
            query_type=nlu_result.tool,
            params=nlu_result.params,
        )
        logger.info(
            "Agent resolved via LLM-first pipeline",
            extra={
                "telegram_event": "agent_route_completed",
                "match_type": "llm_first",
                "tool": nlu_result.tool,
                "latency_ms": round((time.perf_counter() - start) * 1000),
            },
        )
        return agent_result

    def _dispatch_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        user_text: str,
        user: Any | None = None,
    ) -> dict[str, Any] | None:
        """Dispatch to the appropriate deterministic tool and return structured output."""
        try:
            # Tool Registry (new) — with permission check
            if self._tool_registry is not None:
                handler = self._tool_registry.get(tool_name)
                if handler is not None:
                    try:
                        result = self._tool_registry.execute(
                            tool_name,
                            params,
                            user_role=getattr(user, 'role', 'admin'),
                            user_permissions=getattr(user, 'permissions', []),
                        )
                    except PermissionError as exc:
                        logger.warning("Tool %s blocked: %s", tool_name, exc)
                        return {"error": str(exc), "blocked": True}
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result
                    return None

            # Doctor tools
            if tool_name in ("list_doctors", "count_doctors", "doctors_by_sex",
                             "doctors_by_rank", "doctors_by_department"):
                if self._doctor_query_service is not None:
                    result = self._doctor_query_service.execute(user_text, params)
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result

            if tool_name in ("doctor_last_service", "doctor_service_load", "unassigned_doctors"):
                if self._semantic_layer_resolver is not None:
                    result = self._semantic_layer_resolver.resolve(
                        user_text=user_text,
                        domain="medicos",
                        action="query",
                        entities=params,
                        is_followup=False,
                        previous_metric=None,
                    )
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result

            # Calendar tools
            if tool_name in ("calendar_assignments", "calendar_assigned_count", "calendar_status"):
                if self._calendar_query_service is not None:
                    result = self._calendar_query_service.execute(tool_name, params)
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result

            # Mission tools — route through IntentRouter (prevents SQL Agent fallback)
            if tool_name in ("mission_list", "mission_status"):
                if self._router is not None:
                    query_type = (
                        "list_active_missions" if tool_name == "mission_list"
                        else "pending_mission_confirmation"
                    )
                    result = self._router.handle(
                        action="query",
                        query_type=query_type,
                        params=params,
                        user_message=user_text,
                    )
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result

            # IntentRouter fallback for registered query types
            if self._router is not None:
                entry = self._router.registry.get(tool_name)
                if entry is not None:
                    result = self._router.handle(
                        action="query",
                        query_type=tool_name,
                        params=params,
                        user_message=user_text,
                    )
                    if result is not None:
                        return result.__dict__ if hasattr(result, '__dict__') else result

            # SQL Agent fallback
            if tool_name == "sql_query":
                result = self._fallback_to_query_db(params.get("question", user_text))
                return result.__dict__ if hasattr(result, '__dict__') else result

            # Last resort: try SQL agent with original text
            if self._query_executor is not None:
                result = self._fallback_to_query_db(user_text)
                return result.__dict__ if hasattr(result, '__dict__') else result

        except Exception:
            logger.warning("Tool dispatch failed for %s", tool_name, exc_info=True)

        return None

    def _generate_nl_response(
        self,
        user_text: str,
        nlu_result: NLUResult,
        tool_result: dict[str, Any] | None,
        history: list[dict],
    ) -> str:
        """Generate natural language response from tool output."""
        try:
            return generate_response(
                self._llm,
                user_text,
                nlu_result.tool,
                tool_result or {},
                history,
            )
        except Exception:
            logger.warning("NL response generation failed, using fallback")
            if tool_result and isinstance(tool_result, dict):
                rows = tool_result.get("rows", tool_result.get("data", {}).get("rows", []))
                columns = tool_result.get("columns", tool_result.get("data", {}).get("columns", []))
                if rows:
                    return _format_rows(rows, columns)
            return "No se encontraron resultados." if not tool_result else str(tool_result)

    def _handle_reply(self, text: str, nlu_result: NLUResult) -> AgentResult:
        """Handle conversational replies (greetings, help, etc.)."""
        response_type = nlu_result.params.get("response_type", "unknown")
        if response_type == "greeting":
            return AgentResult(
                response_text="¡Hola! Soy el asistente de turnos médicos. ¿En qué puedo ayudarte?",
                agent_action="reply",
            )
        if response_type == "help":
            return AgentResult(
                response_text=(
                    "Puedes consultarme sobre:\n"
                    "• Doctores disponibles y sus horarios\n"
                    "• Calendarios de guardias\n"
                    "• Misiones médicas\n"
                    "• Carga de servicio por doctor\n\n"
                    "Ejemplos:\n"
                    "• \"¿Cuántos doctores hay en cirugía?\"\n"
                    "• \"¿Quiénes están de guardia el lunes?\"\n"
                    "• \"Muéstrame las doctoras disponibles\""
                ),
                agent_action="reply",
            )
        if response_type == "farewell":
            return AgentResult(
                response_text="¡Hasta luego! Estoy aquí cuando me necesites.",
                agent_action="reply",
            )
        return AgentResult(
            response_text="¿En qué más puedo ayudarte con los turnos médicos?",
            agent_action="reply",
        )

    # ------------------------------------------------------------------
    # Legacy pipeline (fallback)
    # ------------------------------------------------------------------

    def _process_legacy(
        self,
        text: str,
        telegram_user_id: str | None,
        history: list[dict],
        start: float,
    ) -> AgentResult:
        """Legacy pipeline: EntityResolver + IntentClassifier + if-elif routing chain."""

        # Pre-process entities
        entity_hints = ""
        resolved_entities: dict = {}
        if self._entity_resolver is not None:
            try:
                pre = self._entity_resolver.pre_process(text)
                entity_hints = pre.get("hints", "")
                resolved_entities = pre.get("resolved", {})
            except Exception:
                logger.warning("EntityResolver.pre_process failed", exc_info=True)

        (
            resolved_entities,
            entity_hints,
            context_applied,
            followup_operation,
        ) = self._merge_followup_context(
            telegram_user_id, resolved_entities, entity_hints, text,
        )

        mission_followup = self._mission_contextual_followup_result(text, telegram_user_id)
        if mission_followup is not None:
            self._remember_result(
                telegram_user_id, mission_followup,
                query_type=(mission_followup.tool_entities or {}).get("query_type"),
                params={},
            )
            return mission_followup

        classified = self._classify_intent(
            text=text,
            entity_hints=entity_hints,
            resolved_entities=resolved_entities,
        )

        if classified.action in ("reply", "ambiguous"):
            return AgentResult(
                response_text=classified.response_text
                or "Necesito que me indiques que informacion del sistema quieres consultar.",
                agent_action=classified.action,
            )

        # Semantic Layer
        if classified.metric and self._semantic_layer_resolver is not None:
            try:
                entities_for_semantic = dict(resolved_entities)
                entities_for_semantic.update(classified.params)
                semantic_result = self._semantic_layer_resolver.resolve(
                    user_text=text, domain=classified.domain, action=classified.action,
                    entities=entities_for_semantic, is_followup=False, previous_metric=None,
                )
                if semantic_result is not None:
                    agent_result = self._semantic_layer_resolver.to_agent_result(
                        semantic_result, user_text=text, format=classified.format,
                    )
                    self._remember_result(
                        telegram_user_id, agent_result,
                        query_type=f"semantic:{semantic_result.metric_name}",
                        params=classified.params,
                    )
                    return agent_result
            except Exception:
                logger.warning("SemanticLayerResolver failed", exc_info=True)

        # Doctor query
        if classified.domain == "medicos" and self._doctor_query_service is not None:
            try:
                result = self._doctor_query_service.execute(text, resolved_entities)
                if result is not None:
                    self._remember_result(telegram_user_id, result)
                    logger.info(
                        "Agent resolved via legacy pipeline",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "legacy_doctor_query",
                        },
                    )
                    return result
            except Exception:
                logger.warning("DoctorQueryService failed", exc_info=True)

        # Calendar query
        if classified.domain == "calendario" and self._calendar_query_service is not None:
            try:
                result = self._calendar_query_service.execute(
                    classified.query_type or "list_calendar_assignments", classified.params,
                )
                if result is not None:
                    self._remember_result(
                        telegram_user_id, result,
                        query_type=classified.query_type or "list_calendar_assignments",
                        params=classified.params,
                    )
                    logger.info(
                        "Agent resolved via legacy pipeline",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "legacy_calendar_query",
                        },
                    )
                    return result
            except Exception:
                logger.warning("CalendarQueryService failed", exc_info=True)

        # IntentRouter
        if classified.query_type:
            router_result = self._route_via_router(
                classified.action if classified.action == "export" else "query",
                classified.query_type, classified.params, text, format=classified.format,
            )
            if router_result is not None:
                self._remember_result(
                    telegram_user_id, router_result,
                    query_type=classified.query_type, params=classified.params,
                )
                logger.info(
                    "Agent resolved via legacy pipeline",
                    extra={
                        "telegram_event": "agent_route_completed",
                        "match_type": "legacy_intent_router",
                    },
                )
                return router_result

        # QueryExecutor fallback
        if _count_filter_dims(entity_hints) >= 1 and self._query_executor is not None:
            result = self._fallback_to_query_db(text, entity_hints=entity_hints)
            self._remember_result(telegram_user_id, result)
            return result

        return AgentResult(
            response_text=(
                classified.response_text
                or "No estoy seguro de haber entendido. ¿Podrias ser mas especifico?"
            ),
            agent_action="ambiguous",
        )
