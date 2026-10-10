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
        TelegramNotificationProvider,
        FakeProvider,
    )
    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.infrastructure.repositories.action_alerts import (
        ActionAlertRepository,
    )

    session = SessionLocal()
    try:
        if settings.telegram_notification_bot_token:
            provider = TelegramNotificationProvider()
        elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
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
    from backend.app.application.notifications.providers import (
        MetaCloudAPIProvider,
        TelegramNotificationProvider,
        FakeProvider,
    )
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
    from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel, CalendarVersionModel
    from sqlalchemy import select as sa_select
    from backend.app.core.config import settings

    now = datetime.now(UTC)
    tomorrow = date.today() + timedelta(days=1)

    session = SessionLocal()
    try:
        assignments = list(
            session.scalars(
                sa_select(CalendarAssignmentModel)
                .join(CalendarVersionModel, CalendarAssignmentModel.calendar_version_id == CalendarVersionModel.id)
                .where(
                    CalendarAssignmentModel.service_date == tomorrow,
                    CalendarVersionModel.deleted_at.is_(None),
                )
            )
        )
        from backend.app.application.notifications.templates import with_telegram_buttons
        from backend.app.infrastructure.db.models.confirmations import (
            ConfirmationRequestModel,
        )

        sent = 0
        for a in assignments:
            doctor = session.get(DoctorModel, a.doctor_id)
            if not doctor:
                continue
            recipient = doctor.telegram_chat_id or None
            if not recipient:
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
            hour_12 = start_dt.hour % 12 or 12
            ampm = "AM" if start_dt.hour < 12 else "PM"
            start_str = f"{hour_12}:{start_dt.minute:02d} {ampm}"

            message = render_twelve_hour_reminder(
                service_date=str(a.service_date),
                service_area=area_name,
                service_start=start_str,
            )

            # Build payload — use Telegram inline button when possible
            msg_payload: str | dict = message
            if doctor.telegram_chat_id:
                confirmation = session.scalars(
                    sa_select(ConfirmationRequestModel)
                    .where(
                        ConfirmationRequestModel.assignment_id == a.id,
                        ConfirmationRequestModel.status == "pending",
                    )
                    .order_by(ConfirmationRequestModel.created_at.desc())
                    .limit(1)
                ).first()
                if confirmation:
                    msg_payload = with_telegram_buttons(message, confirmation.id)

            if settings.telegram_notification_bot_token:
                provider = TelegramNotificationProvider()
            elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
                provider = MetaCloudAPIProvider()
            else:
                provider = FakeProvider()
            svc = NotificationService(
                repo=NotificationRepository(session),
                provider=provider,
            )
            svc.queue(
                notification_type="reminder_12h",
                idempotency_key=f"reminder_12h:{a.id}:{doctor.id}:{tomorrow.isoformat()}",
                recipient_doctor_id=doctor.id,
                recipient_phone=recipient,
                payload={"message": msg_payload},
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
    """Escalate pending confirmations older than 24 h to supervisors.

    Consolidates all unconfirmed doctors into a single message per supervisor
    instead of sending one message per doctor.
    """
    from datetime import UTC, datetime, timedelta

    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.templates import (
        render_escalamiento_consolidado,
    )
    from backend.app.application.notifications.providers import (
        MetaCloudAPIProvider,
        TelegramNotificationProvider,
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

        if not unconfirmed:
            return {"escalations": 0}

        encargados = session.scalars(
            select(UserModel).where(
                UserModel.active.is_(True),
                UserModel.telegram_chat_id.is_not(None),
                UserModel.permissions.contains(["receive_escalation_alerts"]),
            )
        ).all()

        if not encargados:
            return {"escalations": 0}

        if settings.telegram_notification_bot_token:
            provider = TelegramNotificationProvider()
        elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
            provider = MetaCloudAPIProvider()
        else:
            provider = FakeProvider()
        svc = NotificationService(
            repo=NotificationRepository(session), provider=provider
        )
        doc_repo = DoctorRepository(session)

        # Collect unconfirmed doctor names
        doctor_names: list[str] = []
        for req in unconfirmed:
            doctor = doc_repo.get_by_id(req.doctor_id)
            if doctor:
                doctor_names.append(doctor.name)
            req.escalated_at = datetime.now(UTC)

        if not doctor_names:
            return {"escalations": 0}

        # Send ONE consolidated message per supervisor
        now = datetime.now(UTC)
        import uuid
        message = render_escalamiento_consolidado(doctor_names)
        for encargado in encargados:
            svc.queue(
                notification_type="escalamiento",
                idempotency_key=f"escalamiento:consolidated:{now.strftime('%Y%m%d%H')}:{encargado.id}",
                recipient_doctor_id=None,
                recipient_phone=encargado.telegram_chat_id,
                payload={"message": message},
                created_by=encargado.id,
            )

        session.commit()
        return {"escalations": len(unconfirmed)}
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


def send_license_return_reminders() -> dict:
    """Avisa al encargado de que a un médico se le acaba la ausencia.

    Busca las ausencias con fecha de regreso **dentro de la ventana** (`hoy` .. `hoy + N`,
    con N configurable, 2 por defecto) y, por cada una, deja una alerta en la campana y
    encola el aviso por Telegram a quien tenga el permiso de recibir escalaciones.

    Dos cosas que NO hace, a propósito:

    - **No reactiva a nadie.** No hace falta: la restricción deja de aplicar cuando pasa su
      fecha de fin (decisión 5 del spec).
    - **No incluye las ausencias indefinidas** (`ends_at` nulo): no hay fecha de la que
      avisar.

    La idempotencia la da la clave `license_expiring:{restriccion}:{fecha}`, que incluye la
    fecha de regreso. Eso resuelve los tres casos del spec: la misma fecha avisa **una** vez,
    cambiar la fecha **vuelve a permitir** el aviso, y volver a la fecha anterior **no**
    re-avisa (esa clave ya existe).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from backend.app.application.action_alerts.service import ActionAlertService
    from backend.app.application.catalogs.service import CatalogService
    from backend.app.application.doctors.service_state import sync_service_state
    from backend.app.application.notifications.providers import (
        FakeProvider,
        MetaCloudAPIProvider,
        TelegramNotificationProvider,
    )
    from backend.app.application.notifications.service import NotificationService
    from backend.app.application.notifications.templates import (
        render_license_return_reminder,
    )
    from backend.app.core.config import settings
    from backend.app.infrastructure.db.models.availability import (
        DoctorRestrictionModel,
    )
    from backend.app.infrastructure.db.models.doctors import DoctorModel
    from backend.app.infrastructure.db.models.user import UserModel
    from backend.app.infrastructure.db.session import SessionLocal
    from backend.app.infrastructure.repositories.action_alerts import (
        ActionAlertRepository,
    )
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.notifications import (
        NotificationRepository,
    )

    session = SessionLocal()
    try:
        # Primero el estado, y **antes** de cualquier salida temprana: "activo para servicio" se
        # deriva de las ausencias, así que este es el momento en que un médico sale solo el día
        # que su ausencia empieza y vuelve solo el día que se cumple. Sin esto, el estado solo
        # cambiaría cuando alguien abriera su ficha.
        changed_state = sync_service_state(session)
        if changed_state:
            logger.info(
                "Estado de servicio recalculado para %d médicos: %s",
                len(changed_state), ", ".join(changed_state),
            )

        days = CatalogService(CatalogRepository(session)).get_license_reminder_days()
        today = datetime.now(UTC).date()
        window_end = today + timedelta(days=days)

        stmt = select(DoctorRestrictionModel).where(
            DoctorRestrictionModel.lifted_at.is_(None),
            DoctorRestrictionModel.ends_at.is_not(None),
            DoctorRestrictionModel.ends_at >= today,
            DoctorRestrictionModel.ends_at <= window_end,
        )
        restrictions = list(session.scalars(stmt))
        if not restrictions:
            session.commit()  # el recálculo del estado también se guarda
            return {"reminders": 0, "alerts_created": 0}

        recipients = session.scalars(
            select(UserModel).where(
                UserModel.active.is_(True),
                UserModel.telegram_chat_id.is_not(None),
                UserModel.permissions.contains(["receive_escalation_alerts"]),
            )
        ).all()

        if settings.telegram_notification_bot_token:
            provider = TelegramNotificationProvider()
        elif settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
            provider = MetaCloudAPIProvider()
        else:
            provider = FakeProvider()
        svc = NotificationService(repo=NotificationRepository(session), provider=provider)
        alert_svc = ActionAlertService(ActionAlertRepository(session))

        catalog_repo = CatalogRepository(session)
        reminders = 0
        alerts_created = 0
        for restriction in restrictions:
            doctor = session.get(DoctorModel, restriction.doctor_id)
            if doctor is None:
                continue
            ends_at = restriction.ends_at
            assert ends_at is not None  # filtrado en la consulta
            days_left = (ends_at - today).days
            reason = (
                catalog_repo.get_deactivation_reason_by_id(restriction.reason_id)
                if restriction.reason_id
                else None
            )
            reason_name = reason.display_name if reason is not None else None
            message = render_license_return_reminder(
                doctor.name, reason_name, ends_at.isoformat(), days_left
            )

            # Campana: una alerta abierta por ausencia, visible y resoluble. Si la fecha se
            # editó y la alerta seguía abierta, se reescribe: no puede quedar mostrando una
            # fecha de reintegro vieja.
            before = alert_svc.repo.get_open_for_entity(
                alert_type="license_return_due",
                entity_type="restriction",
                entity_id=restriction.id,
            )
            if before is not None:
                if before.message != message:
                    before.message = message
                    before.alert_metadata = {
                        "doctor_id": doctor.id,
                        "doctor_name": doctor.name,
                        "reason": reason_name,
                        "return_date": ends_at.isoformat(),
                    }
                    before.updated_at = datetime.now(UTC)
            else:
                alerts_created += 1
                alert_svc.create_if_missing(
                    alert_type="license_return_due",
                    section="doctors",
                    severity="info",
                    title="Se acerca el reintegro de un médico",
                    message=message,
                    entity_type="restriction",
                    entity_id=restriction.id,
                    action_url=f"/doctors?doctor={doctor.id}",
                    alert_metadata={
                        "doctor_id": doctor.id,
                        "doctor_name": doctor.name,
                        "reason": reason_name,
                        "return_date": ends_at.isoformat(),
                    },
                )

            # Telegram: un aviso por destinatario, con la fecha en la clave.
            for recipient in recipients:
                svc.queue(
                    notification_type="license_return_reminder",
                    idempotency_key=(
                        f"license_expiring:{restriction.id}:{ends_at.isoformat()}:{recipient.id}"
                    ),
                    recipient_doctor_id=None,
                    recipient_phone=recipient.telegram_chat_id,
                    payload={"message": message},
                    created_by=recipient.id,
                )
            reminders += 1

        session.commit()
        return {"reminders": reminders, "alerts_created": alerts_created}
    except Exception:
        session.rollback()
        logger.exception("Failed license return reminder job")
        return {"reminders": 0, "alerts_created": 0}
    finally:
        session.close()
