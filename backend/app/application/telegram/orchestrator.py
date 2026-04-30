from datetime import datetime, timezone
from uuid import uuid4

from backend.app.application.telegram.intent_classifier import IntentClassifier
from backend.app.application.telegram.tools import ToolGateway
from backend.app.infrastructure.db.models.telegram import TelegramInteractionModel
from backend.app.infrastructure.repositories.telegram import TelegramRepository
from backend.app.infrastructure.repositories.users import UserRepository

UTC = timezone.utc

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_MSG_NOT_LINKED = (
    "No estás vinculado al sistema. "
    "Contacta al administrador para vincular tu cuenta de Telegram."
)
_MSG_INACTIVE_ACCOUNT = "Tu cuenta de sistema está inactiva. Contacta al administrador."
_MSG_MUST_CHANGE_PASSWORD = (
    "Debes cambiar tu contraseña temporal antes de usar el asistente."
)
_MSG_OUT_OF_DOMAIN = (
    "No puedo responder eso porque está fuera del alcance del sistema."
)
_MSG_NO_INFO = "No tengo esa información en el sistema."


class TelegramOrchestrator:
    def __init__(
        self,
        telegram_repo: TelegramRepository,
        user_repo: UserRepository,
        classifier: IntentClassifier,
        tools: ToolGateway,
        bot_client,  # TelegramBotClient or FakeBotClient
        llm,  # LLMProvider — kept for future use / injection symmetry
    ) -> None:
        self._telegram_repo = telegram_repo
        self._user_repo = user_repo
        self._classifier = classifier
        self._tools = tools
        self._bot_client = bot_client
        self._llm = llm

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

        # 4. Classify intent
        classification = self._classifier.classify(text)
        intent: str = classification.get("intent", "out_of_domain")
        entities: dict = classification.get("entities") or {}
        confidence: float = float(classification.get("confidence", 0.0))

        # 5. Out-of-domain or low-confidence
        if intent == "out_of_domain" or confidence < 0.5:
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=_MSG_OUT_OF_DOMAIN,
                matched_user_id=user.id,
                user_role=user.role,
                intent_id=intent,
                entities=entities,
                confidence=confidence,
                tool_name=None,
                tool_request=None,
                tool_response=None,
                status="completed",
                fallback_reason="out_of_domain",
            )
            return _MSG_OUT_OF_DOMAIN

        # 6. Confirm mission assignment (two-step write flow)
        if intent == "confirm_mission_assignment":
            result = self._tools.execute("confirm_mission_assignment", entities)
            data: dict = result.get("data", {})
            if data.get("requires_confirmation"):
                response_text = data["message"]
            else:
                response_text = _MSG_NO_INFO
            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=response_text,
                matched_user_id=user.id,
                user_role=user.role,
                intent_id=intent,
                entities=entities,
                confidence=confidence,
                tool_name=intent,
                tool_request=entities,
                tool_response=result,
                status="completed",
                fallback_reason=None,
            )
            return response_text

        # 7. All other intents
        result = self._tools.execute(intent, entities)

        if not result.get("ok"):
            error = result.get("error", "")
            if error == "out_of_domain":
                response_text = _MSG_OUT_OF_DOMAIN
                fallback_reason = "out_of_domain"
            else:
                response_text = _MSG_NO_INFO
                fallback_reason = "tool_error"

            self._log_and_send(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                text=text,
                response_text=response_text,
                matched_user_id=user.id,
                user_role=user.role,
                intent_id=intent,
                entities=entities,
                confidence=confidence,
                tool_name=intent,
                tool_request=entities,
                tool_response=result,
                status="completed",
                fallback_reason=fallback_reason,
            )
            return response_text

        data = result["data"]
        response_text = self._format_response(intent, data)

        self._log_and_send(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            text=text,
            response_text=response_text,
            matched_user_id=user.id,
            user_role=user.role,
            intent_id=intent,
            entities=entities,
            confidence=confidence,
            tool_name=intent,
            tool_request=entities,
            tool_response=result,
            status="completed",
            fallback_reason=None,
        )
        return response_text

    # ------------------------------------------------------------------
    # Response formatter
    # ------------------------------------------------------------------

    def _format_response(self, intent: str, data: dict) -> str:
        if intent == "count_medicos_activos":
            return f"Hay {data['count']} médico(s) activos en servicio."

        if intent == "list_medicos_activos":
            doctors = data.get("doctors", [])
            total = len(doctors)
            lines = [f"• {d['name']} ({d['id'][:8]})" for d in doctors[:10]]
            header = f"Médicos activos en servicio ({total} en total):"
            return "\n".join([header] + lines)

        if intent == "estado_calendario_mes":
            if not data.get("found"):
                return "No hay calendario para ese período."
            month_idx = data.get("month")
            year = data.get("year")
            # month/year may be embedded in entities; fall back gracefully
            mes = _MONTH_NAMES[int(month_idx) - 1] if month_idx else "?"
            anio = year if year else "?"
            status = data.get("status", "?")
            version_number = data.get("version_number")
            version_status = data.get("version_status")
            assignments = data.get("assignments", 0)
            gaps = data.get("gaps", 0)
            version_str = (
                f"versión {version_number} ({version_status})"
                if version_number is not None
                else "sin versión"
            )
            return (
                f"Calendario {mes} {anio}: estado={status}, "
                f"{version_str}, "
                f"{assignments} asignaciones, "
                f"{gaps} huecos sin resolver."
            )

        if intent == "get_mission_candidate_ranking":
            if not data.get("found"):
                return "No hay ranking para ese período."
            month = data.get("month")
            year = data.get("year")
            mes = _MONTH_NAMES[int(month) - 1] if month else "?"
            header = f"Ranking de candidatos {mes} {year if year else '?'}:"
            lines = [
                f"#{e['position']} {e['doctor_id'][:8]} — carga: {e['total_load_score']:.1f}"
                for e in data.get("entries", [])
            ]
            return "\n".join([header] + lines) if lines else header

        if intent == "recommend_mission_candidates":
            if not data.get("found"):
                return "No hay ranking generado para ese período. Genere el calendario primero."
            mission_date = data.get("mission_date", "?")
            header = f"Candidatos recomendados para misión {mission_date}:"
            lines = [
                f"#{c['position']} {c['doctor_id'][:8]} — carga: {c['total_load_score']:.1f}"
                for c in data.get("candidates", [])
            ]
            return "\n".join([header] + lines) if lines else header

        if intent == "historial_medico":
            if not data.get("found"):
                return "No encontré ese médico."
            doctor_name = data.get("doctor_name", "Médico")
            assignments_60d = data.get("assignments_60d", 0)
            load_60d = float(data.get("load_60d", 0.0))
            return (
                f"{doctor_name}: {assignments_60d} servicio(s) en los últimos 60 días, "
                f"carga ponderada: {load_60d:.1f}."
            )

        if intent == "pendientes_disponibilidad_mes":
            count = data.get("count", 0)
            if count == 0:
                return "Todos los médicos tienen disponibilidad registrada."
            pending = data.get("pending", [])
            header = f"{count} médico(s) sin disponibilidad registrada:"
            lines = [f"• {p['name']}" for p in pending]
            return "\n".join([header] + lines)

        # Fallback for any unrecognised intent that passed validation
        return _MSG_NO_INFO

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
