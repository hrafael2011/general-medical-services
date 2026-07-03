import logging
import re
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.input_sanitizer import InputSanitizer
from backend.app.application.telegram.types import AgentResult
from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramUserLinkModel,
)
from backend.app.application.telegram.message_router import (
    TelegramMessageRouter,
)
from backend.app.application.telegram.chitchat import ChitchatHandler
from backend.app.core.config import settings
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository

_MSG_NOT_LINKED = (
    "No estás vinculado al sistema. "
    "Contacta al administrador para vincular tu cuenta de Telegram."
)
_MSG_INACTIVE_ACCOUNT = "Tu cuenta de sistema está inactiva. Contacta al administrador."
_MSG_MUST_CHANGE_PASSWORD = "Debes cambiar tu contraseña temporal antes de usar el asistente."
_CONFIRMATION_COMMAND_RE = re.compile(
    r"^/(recibido|confirmar)\s+([A-Za-z0-9_\-=]+)\s*$",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert nested values to JSON-safe primitives before DB persistence."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


class TelegramOrchestrator:
    def __init__(
        self,
        telegram_repo: TelegramRepository,
        user_repo: UserRepository,
        agent: ConversationalAgent,
        bot_client,  # TelegramBotClient or FakeBotClient
        report_service=None,
        nlu_engine=None,
    ) -> None:
        self._telegram_repo = telegram_repo
        self._user_repo = user_repo
        self._agent = agent
        self._bot_client = bot_client
        self._report_service = report_service
        self._nlu_engine = nlu_engine
        self._input_sanitizer = InputSanitizer()

    # ------------------------------------------------------------------
    # Routed message pipeline (Phase 3 — feature-flag gated)
    # ------------------------------------------------------------------

    def _route_message(
        self,
        text: str,
        telegram_user_id: str,
        chat_id: int,
        user,
    ) -> str | None:
        """Route message through the new routed path. Returns response or None.

        Returns None when the message should fall through to the legacy agent path.
        Returns a response string when the route was handled directly.

        Per-route feature flags gate each handler independently:
          - FEATURE_TELEGRAM_ROUTER_CHITCHAT -> chitchat handler
          - FEATURE_TELEGRAM_ROUTER_REPORTS -> report contract handler
        When a route's flag is off, the method returns None (fall through to legacy).
        """
        router = TelegramMessageRouter(llm_provider=None)
        decision = router.classify(text)

        import time as _time
        _start = _time.perf_counter()

        logger.info(
            "Telegram route decision",
            extra={
                "telegram_event": "route_decision",
                "telegram_user_id": telegram_user_id,
                "route": decision.route,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "requires_llm": decision.requires_llm,
            },
        )

        # Route: chitchat -> direct deterministic response (gated by per-route flag)
        if decision.route == "chitchat":
            if not settings.feature_telegram_router_chitchat:
                return None  # fall through to legacy agent
            handler = ChitchatHandler()
            result = handler.handle(text)
            if result is not None:
                # _log_and_send handles sending the message, no need for direct send
                self._log_and_send(
                    telegram_user_id=telegram_user_id,
                    chat_id=chat_id,
                    text=text,
                    response_text=result["response_text"],
                    matched_user_id=user.id,
                    user_role=user.role,
                    intent_id=f"chitchat_{result['category']}",
                    entities=None,
                    confidence=result["confidence"],
                    tool_name=None,
                    tool_request=None,
                    tool_response=None,
                    status="completed",
                    fallback_reason=None,
                )
                logger.info(
                    "Telegram interaction completed",
                    extra={
                        "telegram_event": "route_completed",
                        "telegram_user_id": telegram_user_id,
                        "route": "chitchat",
                        "confidence": result["confidence"],
                        "used_llm": False,
                        "used_sql": False,
                        "used_sql_agent": False,
                        "match_type": "chitchat_pattern",
                        "fallback_reason": None,
                        "has_document": False,
                        "latency_ms": round((_time.perf_counter() - _start) * 1000),
                    },
                )
                return result["response_text"]

        # Route: unsupported -> controlled rejection (always on when master flag is on)
        if decision.route == "unsupported":
            rejection_msg = (
                "No puedo responder eso porque está fuera del alcance del sistema."
            )
            self._bot_client.send_message(chat_id, rejection_msg)
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=rejection_msg,
                matched_user_id=user.id,
                user_role=user.role,
                intent_id="unsupported",
                entities=None,
                confidence=decision.confidence,
                tool_name=None,
                tool_request=None,
                tool_response=None,
                status="completed",
                fallback_reason=decision.reason,
            )
            logger.info(
                "Telegram interaction completed",
                extra={
                    "telegram_event": "route_completed",
                    "telegram_user_id": telegram_user_id,
                    "route": "unsupported",
                    "confidence": decision.confidence,
                    "used_llm": False,
                    "used_sql": False,
                    "used_sql_agent": False,
                    "match_type": "deterministic_block",
                    "fallback_reason": decision.reason,
                    "has_document": False,
                    "latency_ms": round((_time.perf_counter() - _start) * 1000),
                },
            )
            return rejection_msg

        # Route: report_request -> gated by per-route flag
        if decision.route == "report_request":
            if not settings.feature_telegram_router_reports:
                return None  # fall through to legacy agent
            return self._try_report_handler(
                text=text,
                decision=decision,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                user=user,
            )

        # Route: operational_query -> try dedicated handler if flag is on
        if decision.route in ("operational_query", "clarification"):
            if not settings.feature_telegram_router_operational:
                return None  # fall through to legacy agent
            result = self._try_operational_handler(
                text=text,
                decision=decision,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                user=user,
            )
            if result is not None:
                return result
            return None  # fall through to legacy agent

        return None

    def _try_operational_handler(self, text, decision, telegram_user_id, chat_id, user):
        """Try to resolve via OperationalQueryHandler with NLUEngine for entity extraction."""
        import time as _htime
        _hstart = _htime.perf_counter()

        from backend.app.application.telegram.operational_query_handler import (
            OperationalQueryHandler,
        )

        handler = OperationalQueryHandler(
            semantic_layer=self._agent._semantic_layer_resolver if hasattr(self._agent, '_semantic_layer_resolver') else None,
            doctor_service=self._agent._doctor_query_service if hasattr(self._agent, '_doctor_query_service') else None,
            calendar_service=self._agent._calendar_query_service if hasattr(self._agent, '_calendar_query_service') else None,
            intent_router=self._agent._router if hasattr(self._agent, '_router') else None,
            sql_executor=self._agent._query_executor if hasattr(self._agent, '_query_executor') else None,
            llm_provider=self._agent._llm if hasattr(self._agent, '_llm') else None,
        )

        # Use NLUEngine for proper domain/entity extraction when available
        domain = "medicos"
        action = "query"
        entities: dict[str, Any] = {"user_text": text}

        if self._nlu_engine:
            try:
                nlu_result = self._nlu_engine.classify(text)
                if nlu_result:
                    # Map tool name to domain
                    tool = nlu_result.tool
                    if tool in ("list_doctors", "count_doctors", "doctors_by_sex",
                                "doctors_by_rank", "doctors_by_department"):
                        domain = "medicos"
                        action = "count" if "count" in tool else "list"
                    elif tool in ("calendar_assignments", "calendar_status"):
                        domain = "calendario"
                    elif tool in ("mission_list", "mission_status"):
                        domain = "misiones"
                    entities.update(nlu_result.params)
                    if nlu_result.needs_clarification:
                        logger.info("NLU requested clarification: %s", nlu_result.clarification_question)
            except Exception as exc:
                logger.warning("NLUEngine classify failed, using keyword fallback", extra={"error": str(exc)})

        if not self._nlu_engine:
            # Fallback keyword-based detection
            import re as _re
            text_lower = text.lower()
            if _re.search(r"\b(calendario|calendario|servicio|turno)\b", text_lower):
                domain = "calendario"
            elif _re.search(r"\b(mision|misiones|misión)\b", text_lower):
                domain = "misiones"
            action = "count" if _re.search(r"\b(cuantos|cuántos|total|numero)\b", text_lower) else "list"

        op_result = handler.resolve(
            user_text=text,
            domain=domain,
            action=action,
            entities=entities,
            telegram_user_id=telegram_user_id,
        )

        if op_result is None:
            logger.info("Operational handler returned None, falling through to legacy")
            return None

        if not op_result.ok:
            return None

        # Send response
        response_text = op_result.response_text
        self._bot_client.send_message(chat_id, response_text)

        # Log interaction
        from datetime import UTC, datetime
        self._log_and_send(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            response_text=response_text,
            matched_user_id=user.id,
            user_role=user.role,
            intent_id=f"operational_{op_result.match_type}",
            entities={"match_type": op_result.match_type, "domain": domain, "action": action},
            confidence=0.8,
            tool_name=op_result.match_type,
            tool_request={"text": text},
            tool_response={},
            status="completed",
            fallback_reason=op_result.fallback_reason,
        )

        _latency = round((_htime.perf_counter() - _hstart) * 1000)
        logger.info(
            "Telegram interaction completed",
            extra={
                "telegram_event": "route_completed",
                "telegram_user_id": telegram_user_id,
                "route": "operational_query",
                "match_type": op_result.match_type,
                "used_sql": op_result.used_sql,
                "used_llm": op_result.used_llm,
                "used_sql_agent": op_result.match_type == "sql_fallback",
                "fallback_reason": op_result.fallback_reason,
                "has_document": False,
                "latency_ms": _latency,
            },
        )
        return response_text

    def _try_report_handler(self, text, decision, telegram_user_id, chat_id, user):
        """Handle a report request via ReportContractValidator + ReportService."""
        import time as _rhtime
        _rhstart = _rhtime.perf_counter()

        from backend.app.application.telegram.report_contracts import (
            TelegramReportRequest,
            ReportContractValidator,
        )
        import re as _re

        # Extract month/year from text
        month_map = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        }
        text_lower = text.lower()
        month = None
        year = None
        for name, num in month_map.items():
            if name in text_lower:
                month = num
                break
        year_match = _re.search(r"\b(20\d{2})\b", text)
        if year_match:
            year = int(year_match.group(1))

        requested_format = decision.requested_format or "pdf"

        # Detect report type from text
        report_type = None
        if "calendario" in text_lower or "calendario" in text_lower:
            report_type = "calendar"
        elif "medico" in text_lower or "médico" in text_lower or "doctor" in text_lower:
            report_type = "doctor_list"
        elif "carga" in text_lower or "workload" in text_lower:
            report_type = "workload"
        elif "cobertura" in text_lower or "coverage" in text_lower:
            report_type = "coverage"
        elif "mision" in text_lower or "ranking" in text_lower:
            report_type = "mission_ranking"

        if report_type is None:
            self._bot_client.send_message(
                chat_id,
                "No reconocí el tipo de reporte. Los disponibles son: calendario, "
                "listado de médicos, carga de trabajo, cobertura y ranking de misiones."
            )
            return "No reconocí el tipo de reporte."

        contract = TelegramReportRequest(
            report_type=report_type,
            output_format=requested_format,
            month=month,
            year=year,
        )
        validator = ReportContractValidator()
        validation = validator.validate(contract)

        if not validation["ok"]:
            self._bot_client.send_message(chat_id, validation["needs"])
            return validation["needs"]

        # Report is valid — generate via ReportService if available
        label_map = {
            "calendar": "calendario",
            "doctor_list": "listado de médicos",
            "workload": "carga de trabajo",
            "coverage": "cobertura",
            "mission_ranking": "ranking de misiones",
        }
        label = label_map.get(report_type, report_type)
        format_label = "PDF" if requested_format == "pdf" else "Excel"
        period = f"{month or ''}/{year or ''}" if month or year else ""

        has_document = False
        if self._report_service:
            try:
                gen_result = validator.generate_report(contract, self._report_service)
                if gen_result.get("ok") and gen_result.get("document_bytes"):
                    doc_bytes = gen_result["document_bytes"]
                    filename = gen_result.get("filename", f"{report_type}.{requested_format}")
                    self._bot_client.send_document(chat_id, doc_bytes, filename)
                    msg = f"{label.capitalize()} en {format_label}"
                    if period:
                        msg += f" para {period}"
                    msg += " generado y enviado."
                    has_document = True
                elif gen_result.get("ok"):
                    msg = f"Datos de {label} generados correctamente."
                else:
                    msg = f"No se pudo generar el {label}: {gen_result.get('error', 'error desconocido')}"
                    self._bot_client.send_message(chat_id, msg)
                    return msg
            except Exception as exc:
                logger.exception("Report generation failed")
                msg = f"No se pudo generar el {label} en este momento. Intenta más tarde."
                self._bot_client.send_message(chat_id, msg)
                return msg
        else:
            msg = f"Generando {label} en {format_label}"
            if period:
                msg += f" para {period}"
            msg += ". En unos momentos lo recibirás."
            self._bot_client.send_message(chat_id, msg)

        _latency = round((_rhtime.perf_counter() - _rhstart) * 1000)
        logger.info(
            "Telegram interaction completed",
            extra={
                "telegram_event": "route_completed",
                "telegram_user_id": telegram_user_id,
                "route": "report_request",
                "report_type": report_type,
                "output_format": requested_format,
                "match_type": "report_contract",
                "used_sql": False,
                "used_llm": False,
                "has_document": has_document,
                "latency_ms": _latency,
            },
        )
        return msg

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def handle_message(
        self,
        *,
        telegram_user_id: str,
        telegram_username: str | None,
        chat_id: int,
        text: str,
    ) -> str:
        """
        Main entry point. Returns the response text sent to the user.
        Always logs the interaction.
        """
        start = time.perf_counter()
        # 0. Handle /start deep-link authentication
        if text.startswith("/start"):
            return self._handle_start_link(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                chat_id=chat_id,
                text=text,
            )

        # 1. Resolve link
        link = self._telegram_repo.get_link_by_telegram_id(telegram_user_id)
        if link is None:
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=_MSG_NOT_LINKED,
                matched_user_id=None,
                user_role=None,
                intent_id=None,
                entities=None,
                confidence=None,
                tool_name=None,
                tool_request=None,
                tool_response=None,
                status="completed",
                fallback_reason="not_linked",
            )
            return _MSG_NOT_LINKED

        # 2. Resolve system user
        user = self._user_repo.get_by_id(link.user_id)
        if user is None or not user.active:
            response_text = _MSG_INACTIVE_ACCOUNT
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=response_text,
                matched_user_id=link.user_id,
                user_role=user.role if user else None,
                intent_id=None,
                entities=None,
                confidence=None,
                tool_name=None,
                tool_request=None,
                tool_response=None,
                status="completed",
                fallback_reason="inactive_user",
            )
            return response_text

        if user.must_change_password:
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=_MSG_MUST_CHANGE_PASSWORD,
                matched_user_id=user.id,
                user_role=user.role,
                intent_id=None,
                entities=None,
                confidence=None,
                tool_name=None,
                tool_request=None,
                tool_response=None,
                status="completed",
                fallback_reason="must_change_password",
            )
            return _MSG_MUST_CHANGE_PASSWORD

        # 3. Update last_used_at
        link.last_used_at = datetime.now(UTC)

        confirmation_response = self._handle_confirmation_command(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            user_id=user.id,
            user_role=user.role,
        )
        if confirmation_response is not None:
            return confirmation_response

        # 4. Sanitize user input before reaching the LLM
        is_safe, sanitized = self._input_sanitizer.sanitize(text)
        if not is_safe:
            logger.warning(
                "Prompt injection blocked",
                extra={"telegram_user_id": telegram_user_id},
            )
            self._bot_client.send_message(chat_id, "⚠️ No puedo procesar esa solicitud.")
            return "⚠️ No puedo procesar esa solicitud."

        # 5. Route through new router if feature flag is enabled
        if settings.feature_telegram_router:
            routed_response = self._route_message(
                text=text,
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                user=user,
            )
            if routed_response is not None:
                return routed_response
            # If _route_message returns None, fall through to legacy agent

        # 6. Process through conversational agent (legacy path)
        result: AgentResult = self._agent.process(
            text=text,
            telegram_user_id=telegram_user_id,
            user_info={"name": user.name, "role": user.role, "id": user.id},
            actor_id=user.id,
            user=user,
        )
        response_text = result.response_text

        # 7. Send document if present
        if result.document_bytes and result.document_filename:
            self._bot_client.send_document(chat_id, result.document_bytes, result.document_filename)
            response_text = f"{response_text}\n\n📎 {result.document_filename}"

        # 8. Log interaction
        self._log_and_send(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            response_text=response_text,
            matched_user_id=user.id,
            user_role=user.role,
            intent_id=f"agent_{result.agent_action}",
            entities=result.tool_entities,
            confidence=None,
            tool_name=result.tool_name,
            tool_request=result.tool_entities,
            tool_response=result.tool_result,
            status="completed",
            fallback_reason=None,
        )
        # Determine observability fields from agent result
        used_sql = result.tool_name in ("sql_query", "intent_router") if result.tool_name else False
        used_sql_agent = result.tool_name == "sql_query" if result.tool_name else False
        match_type = "conversational_agent"
        if result.agent_action == "direct":
            match_type = "direct_reply"
        elif result.tool_name in ("list_doctors", "count_doctors", "doctors_by_sex",
                                    "doctors_by_rank", "doctors_by_department"):
            match_type = "doctor_service"
        elif result.tool_name in ("calendar_assignments", "calendar_assigned_count",
                                    "calendar_status"):
            match_type = "calendar_service"
        elif result.tool_name in ("mission_list", "mission_status"):
            match_type = "mission_service"

        logger.info(
            "Telegram interaction completed",
            extra={
                "telegram_event": "interaction_completed",
                "agent_action": result.agent_action,
                "tool_name": result.tool_name,
                "match_type": match_type,
                "used_sql": used_sql,
                "used_sql_agent": used_sql_agent,
                "has_document": result.document_bytes is not None,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "user_role": user.role,
            },
        )
        return response_text

    def _handle_confirmation_command(
        self,
        *,
        telegram_user_id: str,
        chat_id: int,
        text: str,
        user_id: str,
        user_role: str,
    ) -> str | None:
        match = _CONFIRMATION_COMMAND_RE.match(text.strip())
        if match is None:
            return None

        command = match.group(1).lower()
        response_text = "Las confirmaciones de médicos no se realizan desde cuentas internas."
        self._log_and_send(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            response_text=response_text,
            matched_user_id=user_id,
            user_role=user_role,
            intent_id="confirmation_command",
            entities={"command": command},
            confidence=1.0,
            tool_name="confirmation_service",
            tool_request={"command": command},
            tool_response={"status": "not_authorized_internal_user"},
            status="completed",
            fallback_reason="confirmation_internal_user",
        )
        return response_text

    # ------------------------------------------------------------------
    # Deep-link /start handler
    # ------------------------------------------------------------------

    def _handle_start_link(
        self,
        *,
        telegram_user_id: str,
        telegram_username: str | None,
        chat_id: int,
        text: str,
    ) -> str:
        """Handle /start <token> deep-link authentication."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            msg = (
                "Bienvenido al sistema de turnos médicos. "
                "Para vincular tu cuenta, usa el link de invitación "
                "que te proporcionó el administrador."
            )
            self._bot_client.send_message(chat_id, msg)
            return msg

        token_str = parts[1].strip()
        token_record = self._telegram_repo.get_valid_token(token_str)

        if token_record is None:
            msg = (
                "El link es inválido o ha expirado. "
                "Solicita uno nuevo al administrador."
            )
            self._bot_client.send_message(chat_id, msg)
            return msg

        linked_user = self._user_repo.get_by_id(token_record.user_id)
        if linked_user is None or linked_user.role not in {"admin", "encargado"}:
            msg = "Este link no corresponde a un usuario autorizado para Telegram."
            self._bot_client.send_message(chat_id, msg)
            return msg

        existing_by_user = self._telegram_repo.get_link_by_user_id(token_record.user_id)
        if existing_by_user is not None:
            self._telegram_repo.mark_token_used(token_record.id)
            msg = "Ya estás vinculado al sistema."
            self._bot_client.send_message(chat_id, msg)
            return msg

        existing_by_telegram = self._telegram_repo.get_link_by_telegram_id(telegram_user_id)
        if existing_by_telegram is not None:
            self._telegram_repo.mark_token_used(token_record.id)
            if existing_by_telegram.active:
                msg = "Esta cuenta de Telegram ya está vinculada a otro usuario."
            else:
                # Reactivate the inactive link and update its user
                existing_by_telegram.user_id = token_record.user_id
                existing_by_telegram.active = True
                existing_by_telegram.linked_by = token_record.created_by
                existing_by_telegram.linked_at = datetime.now(UTC)
                existing_by_telegram.last_used_at = datetime.now(UTC)
                existing_by_telegram.telegram_username = telegram_username
                msg = "¡Vinculación exitosa! Ya puedes usar el asistente de turnos médicos."
            self._bot_client.send_message(chat_id, msg)
            return msg

        # Check for a previously-deactivated link to avoid unique constraint violation
        existing_inactive = self._telegram_repo.get_any_link_by_telegram_id(telegram_user_id)
        if existing_inactive is not None:
            # Reactivate the existing link instead of inserting a new one
            self._telegram_repo.mark_token_used(token_record.id)
            existing_inactive.user_id = token_record.user_id
            existing_inactive.active = True
            existing_inactive.linked_by = token_record.created_by
            existing_inactive.linked_at = datetime.now(UTC)
            existing_inactive.last_used_at = datetime.now(UTC)
            existing_inactive.telegram_username = telegram_username
            msg = "¡Vinculación exitosa! Ya puedes usar el asistente de turnos médicos."
            self._bot_client.send_message(chat_id, msg)
            return msg

        now = datetime.now(UTC)
        link = TelegramUserLinkModel(
            id=str(uuid4()),
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            user_id=token_record.user_id,
            active=True,
            linked_by=token_record.created_by,
            linked_at=now,
            last_used_at=now,
        )
        self._telegram_repo.add_link(link)
        self._telegram_repo.mark_token_used(token_record.id)

        interaction = TelegramInteractionModel(
            id=str(uuid4()),
            telegram_user_id=telegram_user_id,
            matched_user_id=token_record.user_id,
            user_role=None,
            intent_id="start_link",
            input_text=text,
            extracted_entities={"token": token_str[:8] + "..."},
            intent_confidence=1.0,
            tool_name=None,
            tool_request=None,
            tool_response=None,
            response_text="Vinculación exitosa",
            cache_status=None,
            fallback_reason=None,
            status="completed",
            created_at=now,
        )
        self._telegram_repo.add_interaction(interaction)

        msg = (
            "¡Vinculación exitosa! Ya puedes usar el asistente "
            "de turnos médicos."
        )
        self._bot_client.send_message(chat_id, msg)
        return msg

    def send_error(self, chat_id: int, message: str) -> None:
        """Best-effort error notification to a Telegram chat. Never raises."""
        try:
            self._bot_client.send_message(chat_id, message)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helper: log + send
    # ------------------------------------------------------------------

    def _log_and_send(
        self,
        *,
        telegram_user_id: str,
        chat_id: int,
        text: str,
        response_text: str,
        matched_user_id: str | None,
        user_role: str | None,
        intent_id: str | None,
        entities: dict | None,
        confidence: float | None,
        tool_name: str | None,
        tool_request: dict | None,
        tool_response: dict | None,
        status: str,
        fallback_reason: str | None,
    ) -> None:
        # 8. Log interaction
        interaction = TelegramInteractionModel(
            id=str(uuid4()),
            telegram_user_id=telegram_user_id,
            matched_user_id=matched_user_id,
            user_role=user_role,
            intent_id=intent_id,
            input_text=text,
            extracted_entities=_json_safe(entities),
            intent_confidence=confidence,
            tool_name=tool_name,
            tool_request=_json_safe(tool_request),
            tool_response=_json_safe(tool_response),
            response_text=response_text,
            cache_status=None,
            fallback_reason=fallback_reason,
            status=status,
            created_at=datetime.now(UTC),
        )
        self._telegram_repo.add_interaction(interaction)

        # 9. Send via bot client
        self._bot_client.send_message(chat_id, response_text)
