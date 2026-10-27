"""Vencimiento de confirmaciones atado al inicio del servicio."""

from datetime import UTC, datetime, timedelta

from backend.app.application.confirmations.deadlines import due_at_for_service


def test_due_is_four_hours_before_the_service():
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)

    assert due_at_for_service(start, hours_before=4, now=now) == datetime(
        2026, 11, 1, 4, 0, tzinfo=UTC
    )


def test_due_never_lands_in_the_past():
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)

    assert due_at_for_service(start, hours_before=4, now=now) == now + timedelta(hours=1)


def test_without_service_start_the_legacy_fallback_is_kept():
    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)

    assert due_at_for_service(None, hours_before=4, now=now) == now + timedelta(hours=12)
