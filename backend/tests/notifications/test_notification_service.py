"""
DB-backed integration tests for NotificationService.

Uses the in-memory SQLite db_session fixture from conftest.py.
"""

import uuid

from backend.app.application.notifications.providers import FakeProvider
from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.templates import (
    render_initial_assignment,
    render_missing_availability_reminder,
    render_mission_participant,
    render_mission_summary_encargado,
)
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import (
    MAX_RETRIES,
    NotificationRepository,
)

# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------


def _make_service(db_session) -> NotificationService:
    return NotificationService(
        repo=NotificationRepository(db_session),
        provider=FakeProvider(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_key() -> str:
    return f"test-key-{uuid.uuid4().hex}"


def _queue_one(
    service: NotificationService,
    *,
    idempotency_key: str | None = None,
    recipient_phone: str | None = "+18095551234",
    message: str = "Hello doctor",
) -> NotificationEventModel:
    key = idempotency_key or _unique_key()
    return service.queue(
        notification_type="initial_assignment",
        idempotency_key=key,
        recipient_doctor_id=None,
        recipient_phone=recipient_phone,
        payload={"message": message},
        created_by="actor-test",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_queue_creates_notification(db_session) -> None:
    """queue() with a unique key persists a pending notification and returns it."""
    service = _make_service(db_session)
    key = _unique_key()

    event = _queue_one(service, idempotency_key=key)

    assert event.id is not None
    assert event.status == "pending"
    assert event.idempotency_key == key

    # Verify it is retrievable from the DB
    repo = NotificationRepository(db_session)
    fetched = repo.get_by_idempotency_key(key)
    assert fetched is not None
    assert fetched.id == event.id
    assert fetched.status == "pending"


def test_queue_idempotent(db_session) -> None:
    """Calling queue() twice with the same key returns the same record, no duplicate rows."""
    service = _make_service(db_session)
    key = _unique_key()

    first = _queue_one(service, idempotency_key=key)
    second = _queue_one(service, idempotency_key=key)

    assert first.id == second.id

    # Only one row in the DB for this key
    repo = NotificationRepository(db_session)
    all_events = repo.list_all()
    matching = [e for e in all_events if e.idempotency_key == key]
    assert len(matching) == 1


def test_process_sends_pending(db_session) -> None:
    """process_pending() sends a notification with a phone number and marks it sent."""
    provider = FakeProvider()
    service = NotificationService(
        repo=NotificationRepository(db_session),
        provider=provider,
    )

    event = _queue_one(service, recipient_phone="+18095551234")

    result = service.process_pending()

    assert result["sent"] == 1
    assert result["skipped"] == 0
    assert len(provider.sent) == 1
    assert provider.sent[0]["phone"] == "+18095551234"

    # Status must be "sent" in the DB
    repo = NotificationRepository(db_session)
    fetched = repo.get_by_id(event.id)
    assert fetched is not None
    assert fetched.status == "sent"
    assert fetched.sent_at is not None
    assert fetched.provider == "fake"


def test_process_skips_no_phone(db_session) -> None:
    """process_pending() skips notifications without a recipient phone."""
    service = _make_service(db_session)
    _queue_one(service, recipient_phone=None)

    result = service.process_pending()

    assert result["skipped"] == 1
    assert result["sent"] == 0


def test_process_retries_on_failure(db_session) -> None:
    """
    A provider that raises bumps retry_count each call.
    After MAX_RETRIES total calls the status becomes 'failed'.
    """

    class FailingProvider:
        name = "failing"

        def send(self, phone: str, message: str) -> str:
            raise Exception("network error")

    service = NotificationService(
        repo=NotificationRepository(db_session),
        provider=FailingProvider(),
    )

    event = _queue_one(service, recipient_phone="+18095550000")
    repo = NotificationRepository(db_session)

    # First call: retry_count becomes 1, status stays "pending"
    service.process_pending()
    refreshed = repo.get_by_id(event.id)
    assert refreshed is not None
    assert refreshed.retry_count == 1
    assert refreshed.status == "pending"

    # Call process_pending until MAX_RETRIES is exhausted
    # We already called once; need (MAX_RETRIES - 1) more calls
    for _ in range(MAX_RETRIES - 1):
        service.process_pending()

    final = repo.get_by_id(event.id)
    assert final is not None
    assert final.retry_count >= MAX_RETRIES
    assert final.status == "failed"


# ---------------------------------------------------------------------------
# Template rendering — pure Python, no DB
# ---------------------------------------------------------------------------


def test_templates_render_correctly() -> None:
    """Each render function returns Spanish text containing the expected substrings."""
    # initial_assignment
    msg = render_initial_assignment("2026-05-01", "emergencia", None)
    assert "emergencia" in msg
    assert "2026-05-01" in msg

    # mission_participant
    msg = render_mission_participant("2026-05-10", "Base Sur", None, None)
    assert "Base Sur" in msg

    # mission_summary_encargado with participant names
    msg = render_mission_summary_encargado("2026-05-10", None, None, ["doc-1", "doc-2"])
    assert "doc-1" in msg

    # missing_availability_reminder
    msg = render_missing_availability_reminder(["Dr. García"], "27")
    assert "Dr. García" in msg
