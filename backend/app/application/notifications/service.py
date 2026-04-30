from datetime import UTC, datetime
from uuid import uuid4

from backend.app.application.notifications.providers import NotificationProvider
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import (
    MAX_RETRIES,
    NotificationRepository,
)


class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository,
        provider: NotificationProvider,
    ) -> None:
        self.repo = repo
        self.provider = provider

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
        return self.repo.add(event)

    def process_pending(self) -> dict:
        """
        Process up to 50 pending notifications.
        Returns {"sent": int, "failed": int, "skipped": int}.

        For each notification:
          - Skip if no recipient_phone (count as skipped).
          - Call provider.send(phone, payload["message"]).
          - On success: status="sent", sent_at=now, provider=provider.name,
            provider_message_id=msg_id.
          - On failure: status="failed" if retry_count >= MAX_RETRIES else
            status="pending" with retry_count+=1, store error.
        """
        pending = self.repo.list_pending(limit=50)
        sent = 0
        failed = 0
        skipped = 0

        for event in pending:
            if not event.recipient_phone:
                skipped += 1
                continue

            message = (event.payload or {}).get("message", "")
            now = datetime.now(UTC)

            try:
                msg_id = self.provider.send(event.recipient_phone, message)
                event.status = "sent"
                event.sent_at = now
                event.provider = self.provider.name
                event.provider_message_id = msg_id
                event.error_code = None
                event.error_message = None
                event.updated_at = now
                sent += 1
            except Exception as exc:
                event.retry_count += 1
                event.error_message = str(exc)
                event.updated_at = now
                if event.retry_count >= MAX_RETRIES:
                    event.status = "failed"
                    failed += 1
                # else: status remains "pending" for next processing cycle

        return {"sent": sent, "failed": failed, "skipped": skipped}
