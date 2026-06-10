"""Webhook endpoint for @TurnosMedicosBot — doctor linking + confirmations."""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.session import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["telegram-notification"])


@router.post("/telegram-notification")
async def telegram_notification_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Handle incoming updates for @TurnosMedicosBot."""
    body = await request.json()
    logger.debug("Telegram notification webhook: %s", json.dumps(body, default=str))

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
    from uuid import uuid4

    from backend.app.infrastructure.db.models.notifications import (
        NotificationEventModel,
    )

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

    # Create notification event for admin visibility
    event = NotificationEventModel(
        id=str(uuid4()),
        notification_type=f"{req.confirmation_type}_confirmed",
        idempotency_key=f"confirmed:{confirmation_id}",
        recipient_doctor_id=req.doctor_id,
        recipient_phone=None,
        payload={
            "message": (
                f"Dr. confirmó su {'servicio' if req.confirmation_type == 'service' else 'misión'}."
            ),
            "confirmation_request_id": confirmation_id,
        },
        status="skipped",
        sent_at=now,
        created_by=req.doctor_id,
        created_at=now,
        updated_at=now,
    )
    session.add(event)

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
