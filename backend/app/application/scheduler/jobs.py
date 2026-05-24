"""Job functions for the APScheduler notification queue."""

import logging

logger = logging.getLogger(__name__)


def check_unconfirmed_escalamiento() -> dict:
    """Escalate pending confirmations older than 24 h to supervisors with receive_escalation_alerts permission."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from backend.app.application.notifications.providers import FakeProvider
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.templates import (
        render_escalamiento_encargado,
    )
    from backend.app.infrastructure.db.models.confirmations import (
        ConfirmationRequestModel,
    )
    from backend.app.infrastructure.db.models.user import UserModel
    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )

    session = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=24)

        # Find unconfirmed requests older than 24h without escalation
        stmt = (
            select(ConfirmationRequestModel)
            .where(
                ConfirmationRequestModel.status.in_(["pending", "received"]),
                ConfirmationRequestModel.created_at <= cutoff,
                ConfirmationRequestModel.escalated_at.is_(None),
            )
        )
        unconfirmed = list(session.scalars(stmt))

        if not unconfirmed:
            return {"escalations": 0}

        # Find recipients: active users with receive_escalation_alerts permission + admins
        recipients_query = select(UserModel).where(
            UserModel.active.is_(True),
        )
        all_active = session.scalars(recipients_query).all()

        recipients = []
        for u in all_active:
            if u.role == "admin":
                recipients.append(u)
            elif "receive_escalation_alerts" in (u.permissions or []):
                recipients.append(u)

        if not recipients:
            return {"escalations": 0}

        svc = NotificationService(
            repo=NotificationRepository(session), provider=FakeProvider()
        )
        doc_repo = DoctorRepository(session)

        escalated = 0
        for req in unconfirmed:
            doctor = doc_repo.get_by_id(req.doctor_id)
            if not doctor:
                continue
            message = render_escalamiento_encargado(doctor.name)
            for recipient in recipients:
                svc.queue(
                    notification_type="escalamiento",
                    idempotency_key=f"escalamiento:{req.id}:{recipient.id}",
                    recipient_doctor_id=req.doctor_id,
                    recipient_phone=None,
                    payload={"message": message},
                    assignment_id=req.assignment_id,
                    created_by=recipient.id,
                )
            req.escalated_at = datetime.now(UTC)
            escalated += 1

        session.commit()
        return {"escalations": escalated}
    except Exception:
        session.rollback()
        logger.exception("Failed escalamiento check")
        return {"escalations": 0}
    finally:
        session.close()
