from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.notifications import NotificationEventModel

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

    def reactivate_for_assignments(
        self,
        assignment_ids: list[str],
        *,
        scheduled_for: datetime | None = None,
    ) -> list[str]:
        """Devuelve a la cola los avisos que nunca llegaron a salir.

        Cubre `cancelled` (se deshizo la aprobación) y `skipped` (nunca se pudo
        enviar: sin teléfono o sin Telegram). Un aviso descartado no es un
        envío, así que la nueva aprobación lo repone; de lo contrario se queda
        muerto para siempre, porque la clave de idempotencia impide crear otro.

        Lo enviado (`sent`) no se reenvía y lo que está en vuelo (`sending`) no
        se toca. Se reutiliza la fila para no duplicar el aviso.
        """
        if not assignment_ids:
            return []
        now = datetime.now(UTC)
        stmt = select(NotificationEventModel).where(
            NotificationEventModel.assignment_id.in_(assignment_ids),
            NotificationEventModel.status.in_(["cancelled", "skipped"]),
        )
        events = list(self.session.scalars(stmt))
        for event in events:
            event.status = "pending"
            event.retry_count = 0
            event.error_code = None
            event.error_message = None
            event.scheduled_for = scheduled_for
            event.updated_at = now
        self.session.flush()
        return [event.id for event in events]

    def cancel_added_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Cancela los «te asignaron un turno» que aún no salieron.

        Aprobar la semana manda el aviso definitivo; el de asignación suelta
        diría casi lo mismo. Sin esto el médico recibe dos mensajes por el
        mismo turno y el contador de la semana cuenta el doble.
        """
        if not assignment_ids:
            return []
        now = datetime.now(UTC)
        stmt = select(NotificationEventModel).where(
            NotificationEventModel.assignment_id.in_(assignment_ids),
            NotificationEventModel.status == "pending",
            NotificationEventModel.notification_type == "service_assignment_added",
        )
        events = list(self.session.scalars(stmt))
        for event in events:
            event.status = "cancelled"
            event.updated_at = now
        self.session.flush()
        return [event.id for event in events]

    def list_pending_for_assignments(
        self, assignment_ids: list[str]
    ) -> list[NotificationEventModel]:
        """Avisos programados que aún no han salido, de esos turnos.

        Ordenados por hora de salida: el primero es el próximo en irse.
        """
        if not assignment_ids:
            return []
        stmt = (
            select(NotificationEventModel)
            .where(
                NotificationEventModel.assignment_id.in_(assignment_ids),
                NotificationEventModel.status == "pending",
            )
            .order_by(NotificationEventModel.scheduled_for)
        )
        return list(self.session.scalars(stmt))

    def cancel_pending_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Marca `cancelled` los avisos que aún no han salido.

        Nunca toca `sending` (el worker puede tenerlo en vuelo) ni `sent`
        (lo enviado no se recupera). Devuelve los ids cancelados.
        """
        if not assignment_ids:
            return []
        now = datetime.now(UTC)
        stmt = select(NotificationEventModel).where(
            NotificationEventModel.assignment_id.in_(assignment_ids),
            NotificationEventModel.status == "pending",
        )
        events = list(self.session.scalars(stmt))
        for event in events:
            event.status = "cancelled"
            event.updated_at = now
        self.session.flush()
        return [event.id for event in events]

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
