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

logger = logging.getLogger(__name__)

from pydantic import ValidationError

from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import LLMProvider
from backend.app.application.telegram.memory import MemoryManager
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.schemas import IntentOutput
from backend.app.application.telegram.tools import ToolGateway
from backend.app.application.telegram.types import AgentResult


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
- ranks.normalized_name usa valores en minusculas: 'cabo', 'contrata', 'pasante', 'sargento', 'sargento mayor'

Responde UNICAMENTE con JSON en este formato:
{{"action": "query|export|reply|ambiguous", "query_type": "nombre_consulta", "params": {{...}}, "response_text": "...", "format": "pdf|excel"}}

REGLAS:
- Para query/export: elige el query_type mas adecuado de CONSULTAS DISPONIBLES.
- Para reply/ambiguous: incluye response_text con tu respuesta directa.
- Usa los valores EXACTOS de parametros indicados arriba.
- Responde en el MISMO IDIOMA del usuario.
Sin explicaciones ni markdown.
"""


def _format_rows(rows: list[dict], columns: list[str]) -> str:
    """Generate a human-readable response from query results."""
    count = len(rows)
    if count == 0:
        return "No se encontraron resultados."
    if count == 1:
        first = rows[0]
        parts = [f"{k}: {v}" for k, v in first.items() if v is not None]
        return "Resultado: " + " | ".join(parts)
    if count <= 5:
        lines = [
            f"{i+1}. " + " | ".join(str(r.get(c, "")) for c in columns[:3])
            for i, r in enumerate(rows)
        ]
        return f"Se encontraron {count} resultados:\n" + "\n".join(lines)
    lines = [
        f"{i+1}. " + " | ".join(str(r.get(c, "")) for c in columns[:3])
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
        entity_resolver = None,
    ) -> None:
        self._llm = llm
        self._router = router
        self._query_executor = query_executor
        self._tools = tools
        self._memory = memory
        self._entity_resolver = entity_resolver

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

        result = self._query_executor.execute(user_text, user_text)
        if not result.get("ok"):
            return AgentResult(
                response_text="No pude encontrar informacion sobre eso en el sistema.",
                agent_action="query_db",
                tool_result=result,
            )

        data = result["data"]
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        response = _format_rows(rows, columns)

        return AgentResult(
            response_text=response,
            agent_action="query_db",
            tool_result=result,
        )

    # ------------------------------------------------------------------
    # Backward-compat handler for old-format LLM responses
    # ------------------------------------------------------------------

    def _handle_old_tool_format(self, parsed: dict, user_text: str, actor_id: str | None = None) -> AgentResult:
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
        ambiguous_entities: list[dict] = []
        if self._entity_resolver is not None:
            try:
                pre = self._entity_resolver.pre_process(text)
                entity_hints = pre.get("hints", "")
                ambiguous_entities = pre.get("ambiguous", [])
            except Exception:
                logger.warning("EntityResolver.pre_process failed", exc_info=True)

        # 2a. If entity resolver found ambiguity, return it directly
        if ambiguous_entities:
            return AgentResult(
                response_text=ambiguous_entities[0]["question"],
                agent_action="ambiguous",
            )

        # 3. Build prompt (with entity hints)
        system_prompt = self._build_system_prompt(user_info, entity_hints=entity_hints)

        # 4. LLM call
        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        response = self._llm.chat_complete(messages, temperature=0.1, json_mode=True)
        response = response.strip()

        # 4. Parse JSON
        parsed = self._extract_json(response)

        # Not valid JSON → treat as direct reply
        if parsed is None:
            logger.warning("LLM returned invalid JSON: %.200s", response)
            return AgentResult(response_text=response)

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

        # 6a. Reply / ambiguous → direct text
        if action == "reply":
            return AgentResult(
                response_text=response_text or "No tengo informacion sobre eso en el sistema.",
                agent_action="reply",
            )

        if action == "ambiguous":
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
                    return router_result

            # Fallback for query action
            if action == "query":
                fallback = self._fallback_to_query_db(text)
                return fallback

            return AgentResult(
                response_text="No pude encontrar informacion sobre eso en el sistema.",
                agent_action=action,
            )

        # 6c. Unknown action
        logger.warning("LLM returned unknown action '%s' for: %.100s", action, text)
        return AgentResult(response_text="No pude encontrar informacion sobre eso en el sistema.")
