"""Job functions for the APScheduler notification queue.

Each function is a synchronous callable that APScheduler invokes on its
dedicated background thread.  They follow a consistent session lifecycle:
open, try/commit, except/rollback, finally/close.
"""

import logging

logger = logging.getLogger(__name__)


def process_notification_queue() -> dict:
    """Process pending notifications in the queue."""
    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )
    from backend.app.application.notifications.service import NotificationService
    from backend.app.core.config import settings
    from backend.app.application.notifications.providers import (
        MetaCloudAPIProvider,
        FakeProvider,
    )
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.infrastructure.repositories.action_alerts import (
        ActionAlertRepository,
    )

    session = SessionLocal()
    try:
        if settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
            provider = MetaCloudAPIProvider()
        else:
            provider = FakeProvider()
        service = NotificationService(
            repo=NotificationRepository(session),
            provider=provider,
            action_alerts=ActionAlertService(ActionAlertRepository(session)),
        )
        result = service.process_pending()
        session.commit()
        if result["sent"] > 0 or result["failed"] > 0:
            logger.info("Queue processed: %s", result)
        return result
    except Exception:
        session.rollback()
        logger.exception("Failed to process notification queue")
        return {"sent": 0, "failed": 0, "skipped": 0}
    finally:
        session.close()


def send_pre_service_reminders() -> dict:
    """Send pre-service appointment reminders (12 h before start)."""
    from datetime import UTC, datetime, timedelta, date

    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.templates import (
        render_twelve_hour_reminder,
    )
    from backend.app.application.notifications.providers import FakeProvider
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
    from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel
    from sqlalchemy import select as sa_select

    now = datetime.now(UTC)
    tomorrow = date.today() + timedelta(days=1)

    session = SessionLocal()
    try:
        assignments = list(
            session.scalars(
                sa_select(CalendarAssignmentModel).where(
                    CalendarAssignmentModel.service_date == tomorrow
                )
            )
        )
        sent = 0
        for a in assignments:
            doctor = session.get(DoctorModel, a.doctor_id)
            if not doctor or not doctor.whatsapp_phone:
                continue

            if a.service_start_at:
                start_dt = a.service_start_at
            else:
                area = session.get(ServiceAreaModel, a.service_area_id)
                start_hour = area.start_hour if area else 7
                start_dt = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day, start_hour, 0, 0, tzinfo=UTC
                )

            reminder_target = start_dt - timedelta(hours=12)
            window_start = reminder_target - timedelta(minutes=30)
            window_end = reminder_target + timedelta(minutes=30)

            if not (window_start <= now <= window_end):
                continue

            area = session.get(ServiceAreaModel, a.service_area_id)
            area_name = area.display_name if area else str(a.service_area_id)
            start_str = f"{start_dt.hour:02d}:{start_dt.minute:02d}"

            message = render_twelve_hour_reminder(
                service_date=str(a.service_date),
                service_area=area_name,
                service_start=start_str,
            )
            svc = NotificationService(
                repo=NotificationRepository(session),
                provider=FakeProvider(),
            )
            svc.queue(
                notification_type="reminder_12h",
                idempotency_key=f"reminder_12h:{a.id}:{doctor.id}:{tomorrow.isoformat()}",
                recipient_doctor_id=doctor.id,
                recipient_phone=doctor.whatsapp_phone,
                payload={"message": message},
                assignment_id=a.id,
            )
            sent += 1
        session.commit()
        return {"reminders_sent": sent}
    except Exception:
        session.rollback()
        logger.exception("Failed to send pre-service reminders")
        return {"reminders_sent": 0}
    finally:
        session.close()


def check_unconfirmed_escalamiento() -> dict:
    """Escalate pending confirmations older than 24 h to supervisors."""
    from datetime import UTC, datetime, timedelta

    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.confirmations import (
        ConfirmationRequestRepository,
    )
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.templates import (
        render_escalamiento_encargado,
    )
    from backend.app.application.notifications.providers import (
        MetaCloudAPIProvider,
        FakeProvider,
    )
    from backend.app.core.config import settings
    from backend.app.infrastructure.db.models.user import UserModel
    from backend.app.infrastructure.db.models.confirmations import (
        ConfirmationRequestModel,
    )
    from sqlalchemy import select

    session = SessionLocal()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        stmt = (
            select(ConfirmationRequestModel)
            .where(
                ConfirmationRequestModel.status.in_(["pending", "received"]),
                ConfirmationRequestModel.created_at <= cutoff,
                ConfirmationRequestModel.escalated_at.is_(None),
            )
        )
        unconfirmed = list(session.scalars(stmt))

        encargados = session.scalars(
            select(UserModel).where(
                UserModel.active.is_(True),
                UserModel.whatsapp_phone.is_not(None),
                UserModel.permissions.contains(["receive_escalation_alerts"]),
            )
        ).all()

        if not encargados:
            return {"escalations": 0}

        provider = (
            MetaCloudAPIProvider()
            if (settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id)
            else FakeProvider()
        )
        svc = NotificationService(
            repo=NotificationRepository(session), provider=provider
        )
        doc_repo = DoctorRepository(session)

        escalated = 0
        for req in unconfirmed:
            doctor = doc_repo.get_by_id(req.doctor_id)
            if not doctor:
                continue
            message = render_escalamiento_encargado(doctor.name)
            for encargado in encargados:
                svc.queue(
                    notification_type="escalamiento",
                    idempotency_key=f"escalamiento:{req.id}:{encargado.id}",
                    recipient_doctor_id=req.doctor_id,
                    recipient_phone=encargado.whatsapp_phone,
                    payload={"message": message},
                    assignment_id=req.assignment_id,
                    created_by=encargado.id,
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


def process_overdue_confirmations() -> dict:
    """Process overdue confirmation requests."""
    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.confirmations import (
        ConfirmationRequestRepository,
    )
    from backend.app.application.confirmations.service import (
        ConfirmationRequestService,
    )

    session = SessionLocal()
    try:
        service = ConfirmationRequestService(
            ConfirmationRequestRepository(session)
        )
        result = service.process_overdue(actor_id=None)
        session.commit()
        return result
    except Exception:
        session.rollback()
        logger.exception("Failed overdue processing")
        return {"expired": 0, "alerts_created": 0}
    finally:
        session.close()
