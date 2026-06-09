import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.infrastructure.db.session import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Temporary: track webhook calls for staging debugging
_webhook_log: list[dict] = []


@router.get("/whatsapp", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_webhook_verify_token:
        return hub_challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    # Read raw body for HMAC signature validation
    body_bytes = await request.body()

    # Validate X-Hub-Signature-256 from Meta
    _verify_webhook_signature(request, body_bytes)

    body = json.loads(body_bytes)
    try:
        messages = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        for msg in messages:
            _webhook_log.append({
                "from": msg.get("from"),
                "type": msg.get("type"),
                "body": msg.get("text", {}).get("body", "") if msg.get("type") == "text" else None,
                "id": msg.get("id"),
                "ts": str(datetime.now(UTC)),
            })
            if len(_webhook_log) > 20:
                _webhook_log.pop(0)
            if msg.get("type") == "text" and msg["text"]["body"].strip() == "1":
                _confirm_by_phone(session, msg["from"], msg["id"])
    except Exception:
        logger.exception("Error processing WhatsApp webhook")
    return {"status": "ok"}


@router.post("/test-notify")
def test_notify(
    secret: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    import uuid as _uuid
    from datetime import datetime, UTC
    from backend.app.infrastructure.db.models.notifications import NotificationEventModel
    from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from sqlalchemy import select

    try:
        # Find the test doctor
        doctor = session.scalars(
            select(DoctorModel).where(DoctorModel.whatsapp_phone == "8092186876")
        ).first()
        if not doctor:
            raise HTTPException(status_code=400, detail="No doctor with whatsapp_phone=8092186876")

        nid = str(_uuid.uuid4())
        cid = str(_uuid.uuid4())
        token = str(_uuid.uuid4())
        now = datetime.now(UTC)

        # Create notification first (confirmation_request has FK to it)
        notification = NotificationEventModel(
            id=nid,
            notification_type="test",
            recipient_phone="8092186876",
            recipient_doctor_id=doctor.id,
            idempotency_key=f"test:{nid}",
            payload={"message": "Hola Dr. Hendrick Rafael, esta es una prueba de notificacion del sistema de turnos medicos.\n\nResponda 1 para confirmar su turno."},
            status="pending",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        session.add(notification)
        session.commit()  # commit notification first so FK is satisfied

        # Now create confirmation request in a new transaction
        confirm = ConfirmationRequestModel(
            id=cid,
            confirmation_type="test",
            status="pending",
            idempotency_key=f"test-confirm:{cid}",
            response_token=token,
            doctor_id=doctor.id,
            notification_id=nid,
            created_at=now,
            updated_at=now,
        )
        session.add(confirm)
        session.commit()
        return {
            "status": "queued",
            "notification_id": nid,
            "confirmation_id": cid,
            "doctor_id": doctor.id,
            "message": "Notificacion en cola + confirmation request creado. Responde 1 al WhatsApp.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("test-notify error")
        return {"error": str(exc), "type": type(exc).__name__}


@router.get("/diagnostic")
def diagnostic(
    secret: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    from sqlalchemy import text
    notif_rows = session.execute(
        text("SELECT id, notification_type, recipient_phone, status, error_code, error_message, retry_count, provider, created_at, updated_at FROM notification_events ORDER BY created_at DESC LIMIT 5")
    ).fetchall()
    conf_rows = session.execute(
        text("SELECT id, confirmation_type, status, doctor_id, response_channel, responded_at, created_at FROM confirmation_requests ORDER BY created_at DESC LIMIT 5")
    ).fetchall()
    doctor_rows = session.execute(
        text("SELECT id, name, whatsapp_phone FROM doctors WHERE whatsapp_phone IS NOT NULL LIMIT 5")
    ).fetchall()
    return {
        "meta_configured": bool(settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id),
        "api_version": settings.meta_whatsapp_api_version,
        "webhook_verify_token_set": bool(settings.meta_webhook_verify_token),
        "notifications": [
            {
                "id": r[0], "type": r[1], "phone": r[2], "status": r[3],
                "error_code": r[4], "error_message": r[5], "retry_count": r[6],
                "provider": r[7], "created_at": str(r[8]), "updated_at": str(r[9]),
            }
            for r in notif_rows
        ],
        "confirmations": [
            {
                "id": r[0], "type": r[1], "status": r[2], "doctor_id": r[3],
                "response_channel": r[4], "responded_at": str(r[5]) if r[5] else None,
                "created_at": str(r[6]),
            }
            for r in conf_rows
        ],
        "doctors": [
            {"id": r[0], "name": r[1], "whatsapp_phone": r[2]}
            for r in doctor_rows
        ],
        "webhook_log": _webhook_log,
    }


def _verify_webhook_signature(request: Request, body_bytes: bytes) -> None:
    """Validate the X-Hub-Signature-256 header from Meta.

    Meta signs every webhook request with HMAC-SHA256 using the App Secret.
    If the signature is missing or doesn't match, the request is rejected.
    When app_secret is not configured, skips validation with a warning.
    """
    app_secret = settings.meta_whatsapp_app_secret
    if not app_secret:
        logger.warning("Webhook signature verification skipped — META_WHATSAPP_APP_SECRET not configured")
        return

    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = f"sha256={hmac.digest(app_secret.encode(), body_bytes, hashlib.sha256).hex()}"
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")


def _confirm_by_phone(session: Session, sender_phone: str, message_id: str) -> None:
    from datetime import datetime, UTC
    from sqlalchemy import select
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
    from backend.app.application.notifications.phone_utils import phones_match, normalize_phone

    # Find doctor by normalized phone
    doctors = session.scalars(
        select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
    ).all()
    doctor_phones = [(d.name, d.whatsapp_phone, normalize_phone(d.whatsapp_phone)) for d in doctors]
    normalized_sender = normalize_phone(sender_phone)
    doctor = next((d for d in doctors if phones_match(d.whatsapp_phone, sender_phone)), None)

    _webhook_log.append({
        "step": "confirm_by_phone",
        "sender_phone": sender_phone,
        "normalized_sender": normalized_sender,
        "doctor_phones": doctor_phones,
        "doctor_found": doctor.name if doctor else None,
        "ts": str(datetime.now(UTC)),
    })
    if len(_webhook_log) > 20:
        _webhook_log.pop(0)

    if not doctor:
        logger.info("No doctor found for phone %s", sender_phone)
        return

    request = session.scalars(
        select(ConfirmationRequestModel)
        .where(
            ConfirmationRequestModel.doctor_id == doctor.id,
            ConfirmationRequestModel.status.in_(["pending", "received"]),
        )
        .order_by(ConfirmationRequestModel.created_at.desc())
        .limit(1)
    ).first()
    if not request:
        logger.info("No pending confirmation for doctor %s", doctor.name)
        _webhook_log.append({
            "step": "confirm_by_phone",
            "doctor": doctor.name,
            "result": "no_pending_request",
            "ts": str(datetime.now(UTC)),
        })
        return

    request.status = "confirmed"
    request.responded_at = datetime.now(UTC)
    request.response_channel = "whatsapp"
    request.response_payload = {"whatsapp_message_id": message_id, "reply": "1"}
    session.commit()
    logger.info("Doctor %s confirmed via WhatsApp", doctor.name)
