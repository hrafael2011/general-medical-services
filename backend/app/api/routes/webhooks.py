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


@router.get("/diagnostic/doctors")
def diagnostic_doctors(
    secret: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    from sqlalchemy import text
    rows = session.execute(text(
        "SELECT id, name, whatsapp_phone, active, service_active FROM doctors WHERE deleted_at IS NULL LIMIT 20"
    )).fetchall()
    return {
        "count": len(rows),
        "doctors": [
            {"id": r[0], "name": r[1], "whatsapp_phone": r[2], "active": r[3], "service_active": r[4]}
            for r in rows
        ]
    }


@router.post("/diagnostic/run-migration")
def diagnostic_run_migration(
    secret: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    from sqlalchemy import text, inspect
    results = {}
    try:
        engine = session.get_bind()
        with engine.connect() as conn:
            # Check what columns exist
            inspector = inspect(engine)
            cols = {c["name"] for c in inspector.get_columns("doctors")}

            if "phone" in cols:
                # 1. Migrate existing data
                r1 = conn.execute(text(
                    "UPDATE doctors SET whatsapp_phone = phone WHERE whatsapp_phone IS NULL AND phone IS NOT NULL"
                ))
                results["migrated_from_phone"] = r1.rowcount
                # 2. Drop phone column
                conn.execute(text("ALTER TABLE doctors DROP COLUMN phone"))
                results["dropped_phone"] = True
            else:
                results["migrated_from_phone"] = "phone column already removed"

            # 3. Set placeholder for remaining nulls
            r2 = conn.execute(text(
                "UPDATE doctors SET whatsapp_phone = '0000000000' WHERE whatsapp_phone IS NULL"
            ))
            results["set_placeholder"] = r2.rowcount

            # 4. Set NOT NULL
            col_info = inspector.get_columns("doctors")
            w_col = next((c for c in col_info if c["name"] == "whatsapp_phone"), None)
            if w_col and w_col.get("nullable", True):
                conn.execute(text("ALTER TABLE doctors ALTER COLUMN whatsapp_phone SET NOT NULL"))
                results["set_not_null"] = True
            else:
                results["set_not_null"] = "already NOT NULL"

            conn.commit()
        results["status"] = "ok"
    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
    return {"migration": "20260527_0041", "results": results}


@router.post("/diagnostic/set-whatsapp")
def diagnostic_set_whatsapp(
    secret: str = Query(...),
    doctor_id: str = Query(...),
    whatsapp_phone: str = Query(...),
    session: Session = Depends(get_db_session),
) -> dict:
    if secret != "staging-setup-2026":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    from sqlalchemy import text
    result = session.execute(
        text("UPDATE doctors SET whatsapp_phone = :phone, updated_at = NOW() WHERE id = :id AND deleted_at IS NULL"),
        {"phone": whatsapp_phone, "id": doctor_id},
    )
    session.commit()
    return {"updated": result.rowcount, "doctor_id": doctor_id, "whatsapp_phone": whatsapp_phone}


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
