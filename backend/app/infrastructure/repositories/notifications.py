from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.notifications import (
    JobExecutionModel,
    NotificationEventModel,
    ScheduledJobModel,
)

MAX_RETRIES = 3
BACKOFF_SECONDS = 60


def _backoff_seconds(retry_count: int) -> int:
    """Exponential backoff: 60s -> 120s -> 240s."""
    return 60 * (2 ** retry_count)


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
        """Return pending notifications with exponential backoff applied.

        Also recovers events stuck in 'sending' status for more than
        5 minutes (process crashed mid-send).
        """
        now = datetime.now(UTC)
        stuck_cutoff = now - timedelta(minutes=5)
        cutoff = now - timedelta(seconds=BACKOFF_SECONDS)
        stmt = (
            select(NotificationEventModel)
            .where(
                or_(
                    NotificationEventModel.status == "pending",
                    and_(
                        NotificationEventModel.status == "sending",
                        NotificationEventModel.updated_at <= stuck_cutoff,
                    ),
                ),
                NotificationEventModel.retry_count < MAX_RETRIES,
                or_(
                    NotificationEventModel.last_retried_at.is_(None),
                    NotificationEventModel.last_retried_at <= cutoff,
                ),
                or_(
                    NotificationEventModel.scheduled_for.is_(None),
                    NotificationEventModel.scheduled_for <= now,
                ),
            )
            .order_by(NotificationEventModel.created_at)
            .limit(limit)
        )
        candidates = list(self.session.scalars(stmt))

        # Apply exponential backoff per row
        result: list[NotificationEventModel] = []
        for notification in candidates:
            backoff = _backoff_seconds(notification.retry_count)
            retry_cutoff = now - timedelta(seconds=backoff)
            if (
                notification.last_retried_at is None
                or notification.last_retried_at <= retry_cutoff
            ):
                result.append(notification)
            if len(result) >= limit:
                break
        return result

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
