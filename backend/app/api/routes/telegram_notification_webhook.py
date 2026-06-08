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

    # Message (text or contact share)
    msg = body.get("message", {})
    if msg:
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text") or "").strip()

        # /start — show welcome + contact share button
        if text == "/start":
            return _send_telegram_message(
                chat_id,
                "Bienvenido al sistema de turnos medicos.\n\n"
                "Presione el boton para vincularse y recibir sus "
                "notificaciones de turnos.",
                reply_markup={
                    "keyboard": [[
                        {"text": "📱 Compartir contacto", "request_contact": True}
                    ]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                },
            )

        # Contact shared — link doctor
        contact = msg.get("contact")
        if contact:
            phone = _normalize_phone(contact.get("phone_number", ""))
            if not phone:
                return _send_telegram_message(
                    chat_id,
                    "No se pudo leer su numero de telefono. Intente nuevamente.",
                )

            # Match by last 8 digits of whatsapp_phone
            doctors = session.scalars(
                select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
            ).all()
            doctor = next(
                (
                    d for d in doctors
                    if d.whatsapp_phone and (
                        phone.endswith(d.whatsapp_phone[-8:])
                        or d.whatsapp_phone.endswith(phone[-8:])
                    )
                ),
                None,
            )

            if not doctor:
                return _send_telegram_message(
                    chat_id,
                    "No se encontro un medico registrado con ese numero. "
                    "Contacte al encargado.",
                )

            doctor.telegram_chat_id = chat_id
            session.commit()
            logger.info("Doctor %s linked to Telegram chat %s", doctor.name, chat_id)

            return _send_telegram_message(
                chat_id,
                f"Vinculado exitosamente, Dr. {doctor.name}.\n\n"
                "Recibira sus notificaciones de turnos por este medio.",
                reply_markup={"remove_keyboard": True},
            )

        # Unknown text — hint
        return _send_telegram_message(
            chat_id,
            "Use /start para vincularse al sistema de turnos medicos.",
        )

    # Callback query (inline button press for confirmation)
    callback = body.get("callback_query", {})
    if callback:
        chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
        data = callback.get("data", "")

        if data.startswith("confirm:"):
            confirmation_id = data.split(":", 1)[1]
            _process_confirmation(session, chat_id, confirmation_id)
            _answer_callback(callback.get("id", ""))
            return _edit_telegram_message(
                chat_id,
                callback.get("message", {}).get("message_id", 0),
                "✅ Asistencia confirmada. Gracias.",
            )

        _answer_callback(callback.get("id", ""))
        return {"status": "ok"}

    return {"status": "ok"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Remove '+' and non-digit characters."""
    cleaned = phone.removeprefix("+").strip()
    return "".join(c for c in cleaned if c.isdigit())


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

    req.status = "confirmed"
    req.responded_at = datetime.now(UTC)
    req.response_channel = "telegram"
    req.response_payload = {"telegram_chat_id": chat_id}
    session.commit()
    logger.info(
        "Confirmation %s confirmed via Telegram (chat=%s)",
        confirmation_id, chat_id,
    )


def _send_telegram_message(
    chat_id: str, text: str, reply_markup: dict | None = None
) -> dict:
    """Send a message via Telegram Bot API."""
    import httpx

    token = settings.telegram_notification_bot_token
    if not token:
        logger.warning("telegram_notification_bot_token not configured")
        return {"status": "no_token"}

    payload: dict = {"chat_id": chat_id, "text": text}
    if reply_markup:
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


def _edit_telegram_message(
    chat_id: str, message_id: int, text: str
) -> dict:
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


def _answer_callback(callback_query_id: str) -> dict:
    """Answer a callback query to remove the loading spinner."""
    import httpx

    token = settings.telegram_notification_bot_token
    if not token:
        return {"status": "no_token"}

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id},
            timeout=5.0,
        )
        return resp.json()
    except Exception:
        return {"status": "error"}
