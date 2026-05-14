"""Conversational agent — translates natural language to system commands.

Architecture:
  1. Single LLM call translates user message to {action, query_type, params}
  2. IntentRouter executes pre-registered queries (fast path)
  3. QueryExecutor fallback for unregistered questions (slow path)
  4. ToolGateway kept for backward compatibility with old-format responses
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import LLMProvider
from backend.app.application.telegram.memory import MemoryManager, SessionState, SessionStore
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.sanitize import sanitize_text
from backend.app.application.telegram.schemas import IntentOutput
from backend.app.application.telegram.tools import ToolGateway
from backend.app.application.telegram.types import AgentResult

logger = logging.getLogger(__name__)

# Patterns that suggest hallucinated data in reply text
_HALLUCINATION_PATTERNS = [
    # "Tienes N doctores/medicos/..." or "hay N medicos/..."
    re.compile(
        r"(?:tienes?|hay)\s+\d+\s+"
        r"(?:doctor(?:es)?|asignac(?:ion|iones)|medicos?|servicios?)",
        re.IGNORECASE,
    ),
    # Specific doctor name patterns (Dr. / Dra. + capitalized name)
    re.compile(r"(?:Dr\.?|Dra\.?)\s+[A-ZÁÉÍÓÚ][a-záéíóú]+", re.IGNORECASE),
]


def _reply_has_hallucination(text: str) -> bool:
    """Check if *text* contains hallucination patterns."""
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern.search(text):
            return True
    return False


_DATA_REQUEST_PATTERNS = [
    re.compile(
        r"\b(cuant[oa]s?|cauant[oa]s?|lista|dame|muestra|mu[eé]strame|exporta|reporte|pdf|excel)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(m[eé]dicos?|doctores?|cabos?|sargentos?|pasantes?|turnos?|servicios?)\b",
        re.IGNORECASE,
    ),
]

_FOLLOWUP_PATTERNS = [
    re.compile(
        r"\b(y|son|ellos|ellas|eso|esa|esos|esas|mismo|misma|exp[oó]rtalo|exportalo)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(femenin[oa]s?|masculin[oa]s?|pdf|excel|listado|lista)\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+o\s+\d+\b", re.IGNORECASE),
]


_FILTER_DIMS = {
    "rank_id",
    "rank_name",
    "sex",
    "area_id",
    "doctor_id",
    "date",
    "start",
    "department_id",
    "department_name",
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


def _looks_like_data_request(text: str) -> bool:
    """Return True when the user appears to be asking for system data."""
    return all(pattern.search(text) for pattern in _DATA_REQUEST_PATTERNS)


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


def _calendar_assignment_query_intent(text: str) -> tuple[str, dict[str, int]] | None:
    """Map clear monthly assignment questions to safe registered queries."""
    normalized = text.lower()
    period = _extract_month_year(normalized)
    if period is None:
        return None

    mentions_assignment = re.search(
        r"\b(asignad[oa]s?|servicios?|turnos?)\b",
        normalized,
        re.IGNORECASE,
    )
    mentions_doctors = re.search(r"\b(m[eé]dicos?|doctores?)\b", normalized, re.IGNORECASE)
    if not mentions_assignment or not mentions_doctors:
        return None

    month, year = period
    params = {"month": month, "year": year}

    if re.search(r"\b(no|sin)\s+(?:fueron\s+)?asignad", normalized, re.IGNORECASE):
        return "unassigned_doctors_by_month", params
    if re.search(r"\b(cuant[oa]s?|cauant[oa]s?)\b", normalized, re.IGNORECASE):
        return "count_assigned_doctors_by_month", params
    if re.search(r"\b(lista|listado|dame|muestra|mu[eé]strame)\b", normalized, re.IGNORECASE):
        return "list_assigned_doctors_by_month", params
    return None


def _public_columns(columns: list[str]) -> list[str]:
    """Columns safe to show in Telegram text responses."""
    return [
        column for column in columns
        if column.lower() != "id" and not column.lower().endswith("_id")
    ]


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

_SYSTEM_PROMPT = """\
Eres un asistente de un sistema de gestion de turnos medicos.
Traduce el mensaje del usuario a un comando del sistema.

CONSULTAS DISPONIBLES:
{query_types}

ACCIONES:
- query: Ejecutar una consulta para obtener datos del sistema.
- export: Exportar datos a PDF o Excel (cuando piden "reporte", "pdf", "excel").
- reply: Responder directamente (saludos, conversacion general, preguntas fuera del sistema).
- ambiguous: Cuando la consulta no esta clara o falta informacion necesaria.

FORMATO DE EXPORT:
- Incluye "format": "excel" cuando el usuario pide especificamente Excel, XLSX u hoja de calculo.
- Incluye "format": "pdf" cuando pide PDF o no especifica formato.
- Si pide "reporte" sin formato, no incluyas el campo format (se usa PDF por defecto).

VALORES EXACTOS de columnas (usa estos siempre):
- doctors.sex usa 'male' (masculino) y 'female' (femenino)
- ranks.normalized_name usa valores en minusculas:
  'cabo', 'contrata', 'pasante', 'sargento', 'sargento mayor'

Responde UNICAMENTE con JSON en este formato:
{{"action": "query|export|reply|ambiguous", "query_type": "nombre_consulta",
"params": {{...}}, "response_text": "...", "format": "pdf|excel"}}

REGLAS:
- Para query/export: elige el query_type mas adecuado de CONSULTAS DISPONIBLES.
- Para reply/ambiguous: incluye response_text con tu respuesta directa.
- Usa los valores EXACTOS de parametros indicados arriba.
- Responde en el MISMO IDIOMA del usuario.
REGLAS PARA action=reply:
- NUNCA inventes nombres de medicos, cantidades, ni estadisticas.
- NUNCA digas 'tienes X medicos' o 'hay Y servicios' a menos que
  los datos vengan de una consulta SQL ejecutada (action=query).
- Si no estas seguro, usa action=ambiguous y pide clarificacion.
- En modo reply, solo describe tus capacidades en terminos generales.
- NO menciones nombres especificos de doctores a menos que vengan de la BD.
Sin explicaciones ni markdown.
"""


def _format_rows(rows: list[dict], columns: list[str]) -> str:
    """Generate a human-readable response from query results."""
    columns = _public_columns(columns)
    rows = [{column: row.get(column) for column in columns} for row in rows]
    count = len(rows)
    if count == 0:
        return "No se encontraron resultados."
    if count == 1:
        first = rows[0]
        parts = [f"{k}: {sanitize_text(v)}" for k, v in first.items() if v is not None]
        return "Resultado: " + " | ".join(parts)
    if count <= 5:
        lines = [
            f"{i+1}. " + " | ".join(sanitize_text(str(r.get(c, ""))) for c in columns[:3])
            for i, r in enumerate(rows)
        ]
        return f"Se encontraron {count} resultados:\n" + "\n".join(lines)
    lines = [
        f"{i+1}. " + " | ".join(sanitize_text(str(r.get(c, ""))) for c in columns[:3])
        for i, r in enumerate(rows[:5])
    ]
    return f"Se encontraron {count} resultados. Los primeros:\n" + "\n".join(lines)


class ConversationalAgent:
    """LLM-powered conversational agent for the Telegram bot."""

    def __init__(
        self,
        llm: LLMProvider,
        router: IntentRouter,
        query_executor: QueryExecutor | None = None,
        tools: ToolGateway | None = None,
        memory: MemoryManager | None = None,
        session_store: SessionStore | None = None,
        entity_resolver = None,
        doctor_query_service = None,
    ) -> None:
        self._llm = llm
        self._router = router
        self._query_executor = query_executor
        self._tools = tools
        self._memory = memory
        self._session_store = session_store
        self._entity_resolver = entity_resolver
        self._doctor_query_service = doctor_query_service

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_system_prompt(self, user_info: dict | None = None, entity_hints: str = "") -> str:
        query_types_lines = []
        for entry in self._router.registry.list_all():
            params_str = (
                ", ".join(f"{k}: {v}" for k, v in entry["params_schema"].items())
                or "ninguno"
            )
            query_types_lines.append(
                f"- {entry['query_type']}: {entry['description']} "
                f"Params: {params_str}"
            )

        prompt = _SYSTEM_PROMPT.format(
            query_types="\n".join(query_types_lines)
        )

        if entity_hints:
            prompt += (
                f"\n\nENTIDADES DETECTADAS:\n{entity_hints}\n"
                f"Usa estos IDs/valores reales para generar parametros, no los nombres textuales."
            )

        if user_info:
            prompt += (
                f"\n\nInformacion del usuario:\n"
                f"Nombre: {user_info.get('name', 'Desconocido')}\n"
                f"Rol: {user_info.get('role', 'Desconocido')}\n"
            )

        return prompt

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Extract JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        code_block = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL
        )
        if code_block:
            text = code_block.group(1)

        if text.startswith("{") and text.endswith("}"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None
        return None

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
            if result.response_text.startswith("No pude encontrar"):
                return None
            return result
        except Exception:
            return None

    def _fallback_to_query_db(self, user_text: str) -> AgentResult:
        """Fallback: use QueryExecutor for NL-to-SQL."""
        if self._query_executor is None:
            return AgentResult(
                response_text="No pude encontrar informacion sobre eso en el sistema."
            )

        start = time.perf_counter()
        result = self._query_executor.execute(user_text, user_text)
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
        response = _format_rows(rows, columns)

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

        state = SessionState(
            last_query_type=query_type,
            last_params=params or {},
            last_results=rows[:50],
            last_filters=filters,
            last_tool_name=result.tool_name,
            last_agent_action=result.agent_action,
            last_operation=(result.tool_entities or {}).get("operation"),
            last_total=last_total,
            last_document_format=document_format,
        )
        self._session_store.set(telegram_user_id, state)

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
        if "rank" in merged and "rank_id" not in entity_hints and "rank_name" not in entity_hints:
            hints_parts.append(f"rank_name='{merged['rank']['normalized_name']}'")
        if "department" in merged and "department_id" not in entity_hints:
            hints_parts.append(f"department_name='{merged['department']['normalized_name']}'")
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

    def _handle_old_tool_format(
        self,
        parsed: dict,
        user_text: str,
        actor_id: str | None = None,
    ) -> AgentResult:
        """Handle legacy {action: 'call_tool', tool: '...', entities: {...}}."""
        tool_name = parsed.get("tool", "")
        entities = dict(parsed.get("entities", {}))
        # Inject actor_id for write operations (create_mission, etc.)
        if actor_id:
            entities["_actor_id"] = actor_id

        if self._tools is None:
            return AgentResult(
                response_text="No tengo informacion sobre eso en el sistema."
            )

        result = self._tools.execute(tool_name, entities)

        if not result.get("ok"):
            error = result.get("error", "")
            if error == "out_of_domain":
                return AgentResult(
                    response_text="No tengo informacion sobre eso en el sistema.",
                    agent_action="call_tool",
                    tool_name=tool_name,
                    tool_entities=entities,
                    tool_result=result,
                )
            return AgentResult(
                response_text="Ocurrio un error al consultar los datos. Intenta de nuevo.",
                agent_action="call_tool",
                tool_name=tool_name,
                tool_entities=entities,
                tool_result=result,
            )

        data = result["data"]

        # Two-step confirmation flow
        if isinstance(data, dict) and data.get("requires_confirmation"):
            return AgentResult(
                response_text=data.get("message", "Confirma la accion para continuar."),
                agent_action="call_tool",
                tool_name=tool_name,
                tool_entities=entities,
                tool_result=result,
            )

        # Document response (PDF/Excel)
        document_bytes = result.get("document_bytes")
        document_filename = result.get("document_filename")
        if document_bytes and document_filename:
            return AgentResult(
                response_text="Aqui tienes el reporte solicitado.",
                document_bytes=document_bytes,
                document_filename=document_filename,
                agent_action="call_tool",
                tool_name=tool_name,
                tool_entities=entities,
                tool_result=result,
            )

        # Plain data — format via LLM (legacy 2nd call)
        data_str = json.dumps(data, ensure_ascii=False, default=str)
        format_prompt = (
            "Con los siguientes datos del sistema de turnos medicos, "
            "genera una respuesta natural y amigable para el medico.\n\n"
            f"DATOS:\n{data_str}\n\n"
            f"Pregunta original: {user_text}\n\n"
            "Responde en el mismo idioma que la pregunta original, "
            "de forma clara y concisa."
        )
        format_messages = [
            {
                "role": "system",
                "content": (
                    "Eres un asistente amable que explica datos del sistema "
                    "de turnos medicos. Responde en el mismo idioma "
                    "de la pregunta original, de forma clara y concisa."
                ),
            },
            {"role": "user", "content": format_prompt},
        ]

        response = self._llm.chat_complete(format_messages, temperature=0.3)
        return AgentResult(
            response_text=response.strip(),
            agent_action="call_tool",
            tool_name=tool_name,
            tool_entities=entities,
            tool_result=result,
        )

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

        # 2a. If entity resolver found ambiguity, return it directly
        if ambiguous_entities:
            return AgentResult(
                response_text=ambiguous_entities[0]["question"],
                agent_action="ambiguous",
            )

        calendar_query = _calendar_assignment_query_intent(text)
        if calendar_query is not None:
            query_type, params = calendar_query
            router_result = self._route_via_router("query", query_type, params, text)
            if router_result is not None:
                self._remember_result(
                    telegram_user_id,
                    router_result,
                    query_type=query_type,
                    params=params,
                )
                logger.info(
                    "Agent resolved via deterministic calendar assignment query",
                    extra={
                        "telegram_event": "agent_route_completed",
                        "match_type": "deterministic_calendar",
                        "agent_action": router_result.agent_action,
                        "query_type": query_type,
                        "latency_ms": round((time.perf_counter() - start) * 1000),
                    },
                )
                return router_result

        # 2b. Compound doctor queries: deterministic path first, NL-to-SQL fallback second.
        if _count_filter_dims(entity_hints) >= 2 and self._doctor_query_service is not None:
            doctor_query_text = text
            asks_followup_count = bool(
                re.search(r"\b\d+\s+o\s+\d+\b", text, re.IGNORECASE)
                or re.search(r"\bson\b", text, re.IGNORECASE)
            )
            if context_applied and (
                followup_operation in {"count", "count_by_sex"} or asks_followup_count
            ):
                doctor_query_text = f"cuantos {text}"
            result = self._doctor_query_service.execute(doctor_query_text, resolved_entities)
            if result is not None:
                self._remember_result(telegram_user_id, result)
                logger.info(
                    "Agent resolved via deterministic doctor query",
                    extra={
                        "telegram_event": "agent_route_completed",
                        "match_type": "deterministic",
                        "agent_action": result.agent_action,
                        "latency_ms": round((time.perf_counter() - start) * 1000),
                    },
                )
                return result

        if _count_filter_dims(entity_hints) >= 2 and self._query_executor is not None:
            logger.info(
                "Compound query detected (hints=%s), routing to QueryExecutor", entity_hints
            )
            result = self._fallback_to_query_db(text)
            self._remember_result(telegram_user_id, result)
            logger.info(
                "Agent resolved via compound fallback",
                extra={
                    "telegram_event": "agent_route_completed",
                    "match_type": "fallback",
                    "agent_action": result.agent_action,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                },
            )
            return result

        # 3. Build prompt (with entity hints)
        system_prompt = self._build_system_prompt(user_info, entity_hints=entity_hints)

        # 4. LLM call
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        response = self._llm.chat_complete(messages, temperature=0.0, json_mode=True)
        response = response.strip()

        # 4. Parse JSON
        parsed = self._extract_json(response)

        # Not valid JSON → retry once without json_mode (DeepSeek sometimes returns
        # empty content with json_mode + temperature=0.0)
        if parsed is None:
            logger.warning(
                "LLM returned invalid JSON (len=%s), retrying without json_mode",
                len(response),
            )
            response = self._llm.chat_complete(messages, temperature=0.0, json_mode=False)
            response = response.strip()
            parsed = self._extract_json(response)
            if parsed is None:
                logger.warning("LLM retry also failed: %.200s", response)
                return AgentResult(
                    response_text=(
                        response
                        or "Lo siento, no pude procesar tu consulta. Intenta de nuevo."
                    )
                )

        # 5. Legacy format support
        if parsed.get("action") == "call_tool":
            return self._handle_old_tool_format(parsed, text, actor_id=actor_id)

        # 6. Validate with IntentOutput schema
        try:
            intent = IntentOutput.model_validate(parsed)
        except ValidationError as exc:
            logger.warning("LLM returned invalid IntentOutput: %.200s — %s", response, exc)
            return AgentResult(
                response_text="Ocurrió un error al procesar tu consulta. Intentá de nuevo.",
                agent_action="validation_error",
            )

        # 7. Handle low confidence
        if intent.confidence < 0.6:
            return AgentResult(
                response_text=(
                    intent.response_text
                    or "No estoy seguro de haber entendido correctamente. "
                    "¿Podrías ser más específico?"
                ),
                agent_action="ambiguous",
            )

        # 8. Handle missing fields
        if intent.missing_fields:
            fields_str = ", ".join(intent.missing_fields)
            return AgentResult(
                response_text=(
                    intent.response_text
                    or f"Me falta información: {fields_str}. ¿Podrías indicarme?"
                ),
                agent_action="ambiguous",
            )

        action = intent.action
        query_type = (intent.query_type or "").strip()
        params = intent.params
        response_text = intent.response_text or ""
        fmt = intent.format
        logger.info(
            "LLM intent parsed",
            extra={
                "telegram_event": "llm_intent_parsed",
                "agent_action": action,
                "query_type": query_type,
                "params": params,
                "format": fmt,
                "confidence": intent.confidence,
            },
        )

        # 6a. Reply / ambiguous → direct text
        if action == "reply":
            if _looks_like_data_request(text):
                logger.warning("LLM used reply for a data request, refusing ungrounded answer")
                if self._query_executor is not None:
                    fallback = self._fallback_to_query_db(text)
                    self._remember_result(telegram_user_id, fallback)
                    return fallback
                return AgentResult(
                    response_text=(
                        "Para datos especificos del sistema necesito ejecutar una consulta. "
                        "No voy a responder con informacion no verificada."
                    ),
                    agent_action="ambiguous",
                )
            if _reply_has_hallucination(response_text):
                logger.warning("Reply contained potential hallucination, replaced with generic")
                response_text = (
                    "Puedo ayudarte con informacion del sistema de turnos medicos. "
                    "Para datos especificos, preguntame algo concreto como "
                    "'cuantos medicos activos hay' o 'dame la lista de sargentos'."
                )
            logger.info(
                "Agent returned direct reply",
                extra={
                    "telegram_event": "agent_route_completed",
                    "match_type": "reply",
                    "agent_action": "reply",
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                },
            )
            return AgentResult(
                response_text=response_text or "No tengo informacion sobre eso en el sistema.",
                agent_action="reply",
            )

        if action == "ambiguous":
            logger.info(
                "Agent returned clarification",
                extra={
                    "telegram_event": "agent_route_completed",
                    "match_type": "clarification",
                    "agent_action": "ambiguous",
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                },
            )
            return AgentResult(
                response_text=(
                    response_text
                    or "Necesito un poco mas de detalle para ayudarte. "
                       "¿Podrias ser mas especifico?"
                ),
                agent_action="ambiguous",
            )

        # 6b. Query / export → try router, fallback to query_db
        if action in ("query", "export"):
            if query_type:
                router_result = self._route_via_router(action, query_type, params, text, format=fmt)
                if router_result is not None:
                    self._remember_result(
                        telegram_user_id,
                        router_result,
                        query_type=query_type,
                        params=params,
                    )
                    logger.info(
                        "Agent resolved via query registry",
                        extra={
                            "telegram_event": "agent_route_completed",
                            "match_type": "registry",
                            "agent_action": router_result.agent_action,
                            "query_type": query_type,
                            "latency_ms": round((time.perf_counter() - start) * 1000),
                        },
                    )
                    return router_result

            # Fallback for query/export action
            if action in ("query", "export"):
                fallback = self._fallback_to_query_db(text)
                self._remember_result(telegram_user_id, fallback)
                logger.info(
                    "Agent resolved via %s fallback", action,
                    extra={
                        "telegram_event": "agent_route_completed",
                        "match_type": "fallback",
                        "agent_action": fallback.agent_action,
                        "latency_ms": round((time.perf_counter() - start) * 1000),
                    },
                )
                return fallback

        # 6c. Unknown action
        logger.warning("LLM returned unknown action '%s' for: %.100s", action, text)
        return AgentResult(response_text="No pude encontrar informacion sobre eso en el sistema.")
