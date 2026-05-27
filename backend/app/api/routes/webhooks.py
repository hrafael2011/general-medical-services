import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.infrastructure.db.session import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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
    body = await request.json()
    try:
        messages = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        for msg in messages:
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
    nid = str(_uuid.uuid4())
    now = datetime.now(UTC)
    notification = NotificationEventModel(
        id=nid,
        notification_type="test",
        recipient_phone="8092186876",
        idempotency_key=f"test:{nid}",
        payload={"message": "Hola Dr. Hendrick Rafael, esta es una prueba de notificacion del sistema de turnos medicos.\n\nResponda 1 para confirmar su turno."},
        status="pending",
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(notification)
    session.commit()
    return {"status": "queued", "notification_id": nid, "message": "Notificacion en cola. El scheduler la enviara en max 30s."}


@router.get("/diagnostic")
def diagnostic(
    secret: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    from sqlalchemy import text
    rows = session.execute(
        text("SELECT id, notification_type, recipient_phone, status, error_code, error_message, retry_count, provider, created_at, updated_at FROM notification_events ORDER BY created_at DESC LIMIT 5")
    ).fetchall()
    return {
        "meta_configured": bool(settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id),
        "api_version": settings.meta_whatsapp_api_version,
        "notifications": [
            {
                "id": r[0],
                "type": r[1],
                "phone": r[2],
                "status": r[3],
                "error_code": r[4],
                "error_message": r[5],
                "retry_count": r[6],
                "provider": r[7],
                "created_at": str(r[8]),
                "updated_at": str(r[9]),
            }
            for r in rows
        ],
    }


def _confirm_by_phone(session: Session, sender_phone: str, message_id: str) -> None:
    from datetime import datetime, UTC
    from sqlalchemy import select
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
    from backend.app.application.notifications.phone_utils import phones_match

    # Find doctor by normalized phone
    doctors = session.scalars(
        select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
    ).all()
    doctor = next((d for d in doctors if phones_match(d.whatsapp_phone, sender_phone)), None)
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
        return

    request.status = "confirmed"
    request.responded_at = datetime.now(UTC)
    request.response_channel = "whatsapp"
    request.response_payload = {"whatsapp_message_id": message_id, "reply": "1"}
    session.commit()
    logger.info("Doctor %s confirmed via WhatsApp", doctor.name)
