"""Sin rastro no se puede investigar qué pasó cuando alguien deshizo una aprobación."""

from unittest.mock import MagicMock

from backend.app.application.audit.service import AuditService
from backend.app.infrastructure.repositories.audit import AuditRepository


def test_registra_la_cancelacion(db_session):
    service = AuditService(AuditRepository(db_session))

    event = service.log_notifications_cancelled(
        actor_id="user1",
        calendar=MagicMock(id="cal1"),
        scope="week",
        notification_count=3,
        confirmation_count=2,
    )

    assert event.action_type == "notifications_cancelled"
    assert event.entity_type == "calendar"
    assert event.entity_id == "cal1"
    assert event.after_snapshot == {
        "scope": "week",
        "notifications": 3,
        "confirmations": 2,
    }
