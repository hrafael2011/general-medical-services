"""Webhook endpoint for @TurnosMedicosBot — doctor linking + confirmations."""

import json
import logging
import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["telegram-notification"])

# Rate limiter: 20 req/min per telegram_user_id
_notification_limiter = RateLimiter(max_requests=20, window_seconds=60)

# Holders of this permission receive the operational alerts: escalations, the receipt
# of a doctor's answer, and the licence reminders that reuse this same channel.
_ALERT_PERMISSION = "receive_escalation_alerts"


@router.post("/telegram-notification")
async def telegram_notification_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Handle incoming updates for @TurnosMedicosBot."""
    # ── Auth: validate X-Telegram-Bot-Api-Secret-Token (same pattern as telegram.py) ──
    expected_secret = settings.telegram_webhook_secret
    if not expected_secret:
        logger.error("TELEGRAM_WEBHOOK_SECRET not configured — rejecting notification webhook")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret not configured")
    actual_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not secrets.compare_digest(actual_secret or "", expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    body = await request.json()
    logger.debug("Telegram notification webhook: %s", json.dumps(body, default=str))

    # ── Rate limiting per telegram user ───────────────────────────────────────
    telegram_user_id = ""
    callback = body.get("callback_query", {})
    msg = body.get("message", {})
    if callback:
        telegram_user_id = str(callback.get("from", {}).get("id", ""))
    elif msg:
        telegram_user_id = str(msg.get("from", {}).get("id", ""))
    if telegram_user_id and not _notification_limiter.allow(telegram_user_id):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    # ── Callback query (inline button press) ─────────────────────────────
    callback = body.get("callback_query", {})
    if callback:
        chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
        data = callback.get("data", "")
        message_id = callback.get("message", {}).get("message_id", 0)
        cb_id = callback.get("id", "")

        # Confirmation from notification message
        if data.startswith("confirm:") and not data.startswith("confirm:link"):
            confirmation_id = data.split(":", 1)[1]
            _process_confirmation(session, chat_id, confirmation_id)
            _answer_callback(cb_id)
            return _edit_telegram_message(
                chat_id, message_id, "✅ Asistencia confirmada. Gracias.",
            )

        # Doctor linking: confirm phone number
        if data.startswith("link_phone:"):
            phone = data.split(":", 1)[1]
            doctor = _find_doctor_by_phone(session, phone)

            if not doctor:
                _answer_callback(cb_id, "Numero no encontrado en el sistema")
                return _edit_telegram_message(
                    chat_id, message_id,
                    f"❌ No se encontro un medico registrado con el numero "
                    f"+{phone}.\n\n"
                    "Verifique que sea el mismo numero registrado en el sistema "
                    "y contacte al encargado si el problema persiste.\n\n"
                    "Use /start para intentar de nuevo.",
                )

            # Check if another chat already linked this doctor
            if doctor.telegram_chat_id and doctor.telegram_chat_id != chat_id:
                _answer_callback(cb_id, "Este medico ya esta vinculado a otra cuenta")
                return _edit_telegram_message(
                    chat_id, message_id,
                    f"❌ El Dr. {doctor.name} ya esta vinculado a otra cuenta "
                    "de Telegram.\n\n"
                    "Contacte al encargado si necesita cambiar la vinculacion.",
                )

            doctor.telegram_chat_id = chat_id
            session.commit()
            logger.info("Doctor %s linked to Telegram chat %s", doctor.name, chat_id)

            _answer_callback(cb_id, "Vinculado exitosamente")
            return _edit_telegram_message(
                chat_id, message_id,
                f"✅ Vinculado exitosamente, Dr. {doctor.name}.\n\n"
                "Recibira sus notificaciones de turnos por este medio.",
            )

        # Doctor linking: retry (wrong number)
        if data == "link_retry":
            _answer_callback(cb_id)
            return _edit_telegram_message(
                chat_id, message_id,
                "Escriba su numero de telefono nuevamente.\n"
                "Ejemplo: 8091234567",
            )

        # Unknown callback
        _answer_callback(cb_id)
        return {"status": "ok"}

    # ── Text message ─────────────────────────────────────────────────────
    msg = body.get("message", {})
    if msg:
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text") or "").strip()

        # /start <token> — a system user linking to the ALERTS bot.
        # Their chat id belongs to THIS bot, which is why it is handled here and not in
        # the assistant: a chat id from one bot is not valid for another.
        if text.startswith("/start ") and len(text) > len("/start "):
            token = text.split(maxsplit=1)[1].strip()
            return _send_telegram_message(
                chat_id, _link_staff_by_token(session, chat_id=chat_id, token=token)
            )

        # /start
        if text == "/start":
            existing = _get_linked_doctor(session, chat_id)
            if existing:
                return _send_telegram_message(
                    chat_id,
                    f"Ya esta vinculado, Dr. {existing.name}. "
                    "Recibira sus notificaciones de turnos por este medio.",
                )

            return _send_telegram_message(
                chat_id,
                "Bienvenido al sistema de turnos medicos.\n\n"
                "Escriba su numero de telefono para vincularse.\n"
                "Ejemplo: 8091234567",
            )

        # Already linked
        existing = _get_linked_doctor(session, chat_id)
        if existing:
            return _send_telegram_message(
                chat_id,
                f"Ya esta vinculado, Dr. {existing.name}. "
                "Recibira sus notificaciones de turnos por este medio.",
            )

        # Phone number entered — show confirmation
        if text and _looks_like_phone(text):
            phone = _normalize_phone(text)
            return _send_telegram_message(
                chat_id,
                f"Verifique su numero: +{phone}\n\n"
                "Confirme que este numero es correcto para vincularse.",
                inline_keyboard=[
                    [
                        {"text": "✅ Confirmar", "callback_data": f"link_phone:{phone}"},
                        {"text": "🔄 Corregir", "callback_data": "link_retry"},
                    ]
                ],
            )

        # Not a phone number
        return _send_telegram_message(
            chat_id,
            "No se reconocio un numero de telefono. "
            "Escriba su numero sin guiones ni espacios.\n"
            "Ejemplo: 8091234567\n\n"
            "Use /start para volver a intentar.",
        )

    return {"status": "ok"}


# ── Linking helpers ──────────────────────────────────────────────────────────

def _get_linked_doctor(session: Session, chat_id: str) -> DoctorModel | None:
    """Return the doctor linked to this Telegram chat, if any."""
    return session.scalars(
        select(DoctorModel).where(DoctorModel.telegram_chat_id == chat_id)
    ).first()


def _link_staff_by_token(session: Session, *, chat_id: str, token: str) -> str:
    """Link a system user to the ALERTS bot with a single-use token.

    Writes `users.telegram_chat_id`, which is the field the notification job reads.
    The assistant keeps its own link in `telegram_user_links`; the two bots have
    different chat ids, so the same person can be linked to both without collision.
    """
    from datetime import UTC, datetime

    from backend.app.infrastructure.db.models.telegram import TelegramLinkTokenModel
    from backend.app.infrastructure.db.models.user import UserModel

    record = session.scalars(
        select(TelegramLinkTokenModel).where(TelegramLinkTokenModel.token == token)
    ).first()
    if record is None or not record.active or record.used_at is not None:
        return "Enlace invalido o ya utilizado. Pide uno nuevo al administrador."
    if record.expires_at <= datetime.now(UTC):
        return "El enlace expiro. Pide uno nuevo al administrador."

    user = session.get(UserModel, record.user_id)
    if user is None or not user.active:
        return "La cuenta no esta disponible. Contacta al administrador."

    taken = session.scalars(
        select(UserModel).where(
            UserModel.telegram_chat_id == chat_id, UserModel.id != user.id
        )
    ).first()
    if taken is not None:
        return "Este Telegram ya esta vinculado a otra cuenta."

    user.telegram_chat_id = chat_id
    user.updated_at = datetime.now(UTC)
    record.used_at = datetime.now(UTC)
    session.commit()
    logger.info("System user %s linked to alert chat %s", user.id, chat_id)
    return (
        f"Listo, {user.name}.\n\n"
        "Recibiras por este chat los avisos del sistema (escalaciones y licencias)."
    )


def _queue_receipt_for_encargados(
    session: Session,
    *,
    confirmation_id: str,
    message: str,
    doctor_id: str,
    now,
) -> int:
    """Queue one notice per alert recipient for a doctor's response.

    The old code wrote a single event born with `status="skipped"` and no recipient, so
    the encargado never learned that the doctor had answered. One event per recipient —
    the same shape the escalation job uses — because a notification carries a single
    destination. The key includes the recipient, so a replayed callback adds nothing.
    """
    from backend.app.infrastructure.db.models.notifications import NotificationEventModel
    from backend.app.infrastructure.db.models.user import UserModel

    recipients = session.scalars(
        select(UserModel).where(
            UserModel.active.is_(True),
            UserModel.telegram_chat_id.is_not(None),
            UserModel.permissions.contains([_ALERT_PERMISSION]),
        )
    ).all()

    for user in recipients:
        session.add(
            NotificationEventModel(
                id=str(uuid.uuid4()),
                notification_type="confirmation_receipt",
                idempotency_key=f"confirmed:{confirmation_id}:{user.id}",
                recipient_doctor_id=doctor_id,
                recipient_phone=user.telegram_chat_id,
                payload={"message": message, "confirmation_request_id": confirmation_id},
                status="pending",
                created_by=doctor_id,
                created_at=now,
                updated_at=now,
            )
        )
    return len(recipients)


def _looks_like_phone(text: str) -> bool:
    """Check if text looks like a phone number (digits, spaces, +)."""
    cleaned = text.replace(" ", "").replace("+", "").replace("-", "")
    return len(cleaned) >= 7 and cleaned.isdigit()


def _find_doctor_by_phone(session: Session, phone: str) -> DoctorModel | None:
    """Find a doctor by matching the last 8 digits of whatsapp_phone."""
    doctors = session.scalars(
        select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
    ).all()
    return next(
        (
            d for d in doctors
            if d.whatsapp_phone and (
                phone.endswith(d.whatsapp_phone[-8:])
                or d.whatsapp_phone.endswith(phone[-8:])
            )
        ),
        None,
    )


# ── Confirmation helpers ─────────────────────────────────────────────────────

def _process_confirmation(
    session: Session, chat_id: str, confirmation_id: str
) -> None:
    """Mark a confirmation request as confirmed via Telegram."""
    from datetime import UTC, datetime

    req = session.get(ConfirmationRequestModel, confirmation_id)
    if not req or req.status not in ("pending", "received"):
        logger.info(
            "Confirmation %s not found or already processed (chat=%s)",
            confirmation_id, chat_id,
        )
        return

    now = datetime.now(UTC)
    req.status = "confirmed"
    req.responded_at = now
    req.response_channel = "telegram"
    req.response_payload = {"telegram_chat_id": chat_id}

    # Tell the encargados that the doctor answered. This used to be written with
    # status="skipped" and no recipient, so the record existed but no message was ever
    # sent — the encargado never learned that the doctor had replied.
    message = (
        f"Dr. confirmó su {'servicio' if req.confirmation_type == 'service' else 'misión'}."
    )
    _queue_receipt_for_encargados(
        session,
        confirmation_id=confirmation_id,
        message=message,
        doctor_id=req.doctor_id,
        now=now,
    )

    session.commit()
    logger.info(
        "Confirmation %s confirmed via Telegram (chat=%s)",
        confirmation_id, chat_id,
    )


# ── Telegram Bot API helpers ─────────────────────────────────────────────────

def _send_telegram_message(
    chat_id: str,
    text: str,
    reply_markup: dict | None = None,
    inline_keyboard: list | None = None,
) -> dict:
    """Send a message via Telegram Bot API.

    Args:
        chat_id: Telegram chat ID.
        text: Message text.
        reply_markup: Full reply_markup dict (for custom keyboards, remove, etc.).
        inline_keyboard: Inline keyboard rows (convenience — built into reply_markup).
    """
    import httpx

    token = settings.telegram_notification_bot_token
    if not token:
        logger.warning("telegram_notification_bot_token not configured")
        return {"status": "no_token"}

    payload: dict = {"chat_id": chat_id, "text": text}
    if inline_keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": inline_keyboard})
    elif reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("Failed to send Telegram message to %s", chat_id)
        return {"status": "error"}


def _edit_telegram_message(chat_id: str, message_id: int, text: str) -> dict:
    """Edit a previously sent message."""
    import httpx

    token = settings.telegram_notification_bot_token
    if not token:
        return {"status": "no_token"}

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("Failed to edit Telegram message")
        return {"status": "error"}


def _answer_callback(callback_query_id: str, text: str | None = None) -> dict:
    """Answer a callback query to remove the loading spinner.

    Optionally shows a toast notification with `text`.
    """
    import httpx

    token = settings.telegram_notification_bot_token
    if not token:
        return {"status": "no_token"}

    payload: dict = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = False  # toast, not dialog

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json=payload,
            timeout=5.0,
        )
        return resp.json()
    except Exception:
        return {"status": "error"}


# ── Phone normalization ──────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Remove '+' and non-digit characters."""
    cleaned = phone.removeprefix("+").strip()
    return "".join(c for c in cleaned if c.isdigit())
