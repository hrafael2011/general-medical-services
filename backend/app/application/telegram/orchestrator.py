import logging
import re
import time
from datetime import UTC, datetime
from uuid import uuid4

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.types import AgentResult
from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramUserLinkModel,
)
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


class TelegramOrchestrator:
    def __init__(
        self,
        telegram_repo: TelegramRepository,
        user_repo: UserRepository,
        agent: ConversationalAgent,
        bot_client,  # TelegramBotClient or FakeBotClient
    ) -> None:
        self._telegram_repo = telegram_repo
        self._user_repo = user_repo
        self._agent = agent
        self._bot_client = bot_client

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

        # 4. Process through conversational agent
        result: AgentResult = self._agent.process(
            text=text,
            telegram_user_id=telegram_user_id,
            user_info={"name": user.name, "role": user.role, "id": user.id},
            actor_id=user.id,
        )
        response_text = result.response_text

        # 5. Send document if present (Phase 3+)
        if result.document_bytes and result.document_filename:
            self._bot_client.send_document(chat_id, result.document_bytes, result.document_filename)
            response_text = f"{response_text}\n\n📎 {result.document_filename}"

        # 6. Log interaction
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
        logger.info(
            "Telegram interaction completed",
            extra={
                "telegram_event": "interaction_completed",
                "agent_action": result.agent_action,
                "tool_name": result.tool_name,
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

        existing = self._telegram_repo.get_link_by_user_id(token_record.user_id)
        if existing is not None:
            self._telegram_repo.mark_token_used(token_record.id)
            msg = "Ya estás vinculado al sistema."
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
            extracted_entities=entities,
            intent_confidence=confidence,
            tool_name=tool_name,
            tool_request=tool_request,
            tool_response=tool_response,
            response_text=response_text,
            cache_status=None,
            fallback_reason=fallback_reason,
            status=status,
            created_at=datetime.now(UTC),
        )
        self._telegram_repo.add_interaction(interaction)

        # 9. Send via bot client
        self._bot_client.send_message(chat_id, response_text)
