from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.notifications import (
    JobExecutionModel,
    NotificationEventModel,
    ScheduledJobModel,
)

MAX_RETRIES = 3
BACKOFF_SECONDS = 60


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: NotificationEventModel) -> NotificationEventModel:
        self.session.add(event)
        self.session.flush()
        return event

    def get_by_id(self, event_id: str) -> NotificationEventModel | None:
        return self.session.get(NotificationEventModel, event_id)

    def get_by_idempotency_key(self, key: str) -> NotificationEventModel | None:
        stmt = select(NotificationEventModel).where(
            NotificationEventModel.idempotency_key == key
        )
        return self.session.scalars(stmt).first()

    def list_by_period(self, year: int, month: int) -> list[NotificationEventModel]:
        """Return all notifications created in the given calendar month."""
        from calendar import monthrange
        start = datetime(year, month, 1, tzinfo=UTC)
        last_day = monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=UTC)
        stmt = (
            select(NotificationEventModel)
            .where(
                NotificationEventModel.created_at >= start,
                NotificationEventModel.created_at <= end,
            )
            .order_by(NotificationEventModel.created_at)
        )
        return list(self.session.scalars(stmt))

    def list_pending(self, limit: int = 50) -> list[NotificationEventModel]:
        """Return pending notifications scheduled for now or earlier."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=BACKOFF_SECONDS)
        stmt = (
            select(NotificationEventModel)
            .where(
                NotificationEventModel.status == "pending",
                NotificationEventModel.retry_count < MAX_RETRIES,
                (
                    NotificationEventModel.last_retried_at.is_(None)
                    | (NotificationEventModel.last_retried_at <= cutoff)
                ),
                (NotificationEventModel.scheduled_for.is_(None)) |
                (NotificationEventModel.scheduled_for <= now),
            )
            .order_by(NotificationEventModel.created_at)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_all(
        self,
        status: str | None = None,
        notification_type: str | None = None,
        limit: int = 100,
    ) -> list[NotificationEventModel]:
        stmt = select(NotificationEventModel).order_by(
            NotificationEventModel.created_at.desc()
        )
        if status:
            stmt = stmt.where(NotificationEventModel.status == status)
        if notification_type:
            stmt = stmt.where(NotificationEventModel.notification_type == notification_type)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_job(self, job: ScheduledJobModel) -> ScheduledJobModel:
        self.session.add(job)
        self.session.flush()
        return job

    def get_job_by_id(self, job_id: str) -> ScheduledJobModel | None:
        return self.session.get(ScheduledJobModel, job_id)

    def list_jobs(self, status: str | None = None) -> list[ScheduledJobModel]:
        stmt = select(ScheduledJobModel).order_by(ScheduledJobModel.created_at.desc())
        if status:
            stmt = stmt.where(ScheduledJobModel.status == status)
        return list(self.session.scalars(stmt))

    def add_execution(self, execution: JobExecutionModel) -> JobExecutionModel:
        self.session.add(execution)
        self.session.flush()
        return execution
