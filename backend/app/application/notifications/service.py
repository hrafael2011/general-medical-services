import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.notifications.providers import NotificationProvider
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import (
    MAX_RETRIES,
    NotificationRepository,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository,
        provider: NotificationProvider,
        action_alerts: ActionAlertService | None = None,
    ) -> None:
        self.repo = repo
        self.provider = provider
        self.action_alerts = action_alerts

    def queue(
        self,
        *,
        notification_type: str,
        idempotency_key: str,
        recipient_doctor_id: str | None,
        recipient_phone: str | None,
        payload: dict,
        scheduled_for: datetime | None = None,
        assignment_id: str | None = None,
        mission_id: str | None = None,
        created_by: str | None = None,
    ) -> NotificationEventModel:
        """
        Queue a notification. If idempotency_key already exists, return
        existing record without creating a new one.
        """
        existing = self.repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        event = NotificationEventModel(
            id=str(uuid4()),
            notification_type=notification_type,
            idempotency_key=idempotency_key,
            recipient_doctor_id=recipient_doctor_id,
            recipient_phone=recipient_phone,
            payload=payload,
            scheduled_for=scheduled_for,
            assignment_id=assignment_id,
            mission_id=mission_id,
            status="pending",
            retry_count=0,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        try:
            return self.repo.add(event)
        except IntegrityError:
            self.repo.session.rollback()
            existing = self.repo.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing
            raise

    def process_pending(self) -> dict:
        """
        Process up to 50 pending notifications.
        Returns {"sent": int, "failed": int, "skipped": int}.

        Uses a two-phase commit to prevent duplicate delivery:
          1. Mark as "sending" + commit before provider.send()
          2. Mark as "sent" or "pending" + commit after
        This guarantees no two processes can send the same event,
        even under race conditions or overlapping scheduler runs.
        """
        pending = self.repo.list_pending(limit=50)
        sent = 0
        failed = 0
        skipped = 0

        for event in pending:
            now = datetime.now(UTC)

            if not event.recipient_phone:
                event.status = "skipped"
                event.sent_at = now
                event.updated_at = now
                skipped += 1
                continue

            message = (event.payload or {}).get("message", "")

            # Phase 1: lock this event by marking it "sending"
            event.status = "sending"
            event.updated_at = now
            self.repo.session.commit()

            # Phase 2: send and update final status
            try:
                msg_id = self.provider.send(event.recipient_phone, message)
                event.status = "sent"
                event.sent_at = now
                event.provider = self.provider.name
                event.provider_message_id = msg_id
                event.error_code = None
                event.error_message = None
                event.updated_at = now
                self.repo.session.commit()
                logger.info(
                    "Notification %s sent via %s to %s (idempotency=%s)",
                    event.id, self.provider.name, event.recipient_phone, event.idempotency_key,
                )
                sent += 1
            except Exception as exc:
                self.repo.session.rollback()
                # Re-fetch the event after rollback to get a live object
                event = self.repo.get_by_id(event.id)
                if event is None:
                    logger.error("Notification lost after rollback")
                    failed += 1
                    continue
                event.retry_count += 1
                event.error_code = getattr(exc, "code", None) or getattr(exc, "error_code", None)
                event.error_message = str(exc)
                event.last_retried_at = now
                event.updated_at = now
                if event.retry_count >= MAX_RETRIES:
                    event.status = "failed"
                    self._create_failed_notification_alert(event)
                    logger.error(
                        "Notification %s failed after %d retries: %s",
                        event.id, MAX_RETRIES, exc,
                    )
                    failed += 1
                else:
                    event.status = "pending"
                    logger.warning(
                        "Notification %s retry %d/%d failed: %s",
                        event.id, event.retry_count, MAX_RETRIES, exc,
                    )
                self.repo.session.commit()

        return {"sent": sent, "failed": failed, "skipped": skipped}

    def _create_failed_notification_alert(self, event: NotificationEventModel) -> None:
        if self.action_alerts is None:
            return
        self.action_alerts.create_if_missing(
            alert_type="notification_delivery_failed",
            section="notifications",
            severity="warning",
            title="Notificación fallida",
            message="Una notificación no pudo enviarse después de varios intentos.",
            entity_type="notification_event",
            entity_id=event.id,
            action_url="/notifications",
            alert_metadata={
                "notification_type": event.notification_type,
                "recipient_doctor_id": event.recipient_doctor_id,
                "assignment_id": event.assignment_id,
                "mission_id": event.mission_id,
                "error_code": event.error_code,
            },
            created_by=event.created_by,
        )
