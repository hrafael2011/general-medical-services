"""Cuándo vence una confirmación.

Antes vencía 12 h después de la **aprobación**. Si la semana se aprobaba con días de
anticipación, la confirmación moría mucho antes del turno —y antes del recordatorio—,
de modo que el médico recibía el aviso con un botón que ya no servía y la escalación
nunca se disparaba. El vencimiento se ata ahora al **inicio del servicio**.
"""

from datetime import UTC, datetime, timedelta

LEGACY_FALLBACK_HOURS = 12


def due_at_for_service(
    service_start: datetime | None,
    *,
    hours_before: int,
    now: datetime | None = None,
) -> datetime:
    """Deadline for a confirmation, anchored to the service start.

    A confirmation approved weeks in advance used to expire 12 hours after
    approval, long before the reminder. Anchoring it to the service keeps the
    doctor's window open and makes escalation reachable.
    """
    now = now or datetime.now(UTC)
    if service_start is None:
        return now + timedelta(hours=LEGACY_FALLBACK_HOURS)
    if service_start.tzinfo is None:
        service_start = service_start.replace(tzinfo=UTC)
    due = service_start - timedelta(hours=hours_before)
    return max(due, now + timedelta(hours=1))
