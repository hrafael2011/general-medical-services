"""Tests for week-level notification triggers."""
from datetime import date
from unittest.mock import MagicMock, call, ANY

from backend.app.application.notifications.triggers import NotificationTriggers


class FakeDoctor:
    def __init__(self, id, whatsapp_phone):
        self.id = id
        self.whatsapp_phone = whatsapp_phone


class FakeDoctorRepo:
    def __init__(self):
        self.doctors = {}

    def get_by_id(self, doc_id):
        return self.doctors.get(doc_id)


class FakeNotification:
    def __init__(self, id):
        self.id = id
        self.payload = {"message": ""}


class FakeAssignment:
    def __init__(self, id, doctor_id, service_date, service_area_id):
        self.id = id
        self.doctor_id = doctor_id
        self.service_date = service_date
        self.service_area_id = service_area_id


class FakeWeek:
    def __init__(self, id, calendar_id, calendar_version_id, week_number,
                 label, start_date, end_date, status):
        self.id = id
        self.calendar_id = calendar_id
        self.calendar_version_id = calendar_version_id
        self.week_number = week_number
        self.label = label
        self.start_date = start_date
        self.end_date = end_date
        self.status = status


def test_on_week_approved_queues_notification_per_assignment():
    """on_week_approved queues one notification per assignment in the week."""
    notif_service = MagicMock()
    notif_service.queue.return_value = FakeNotification(id="notif-1")
    confirmation_service = MagicMock()
    doctor_repo = FakeDoctorRepo()
    doctor_repo.doctors["doc1"] = FakeDoctor("doc1", "+18095551234")
    doctor_repo.doctors["doc2"] = FakeDoctor("doc2", "+18095554321")

    triggers = NotificationTriggers(
        notification_service=notif_service,
        doctor_repo=doctor_repo,
        confirmation_service=confirmation_service,
    )

    week = FakeWeek(
        id="week1", calendar_id="cal1", calendar_version_id="ver1",
        week_number=1, label="1RA SEMANA",
        start_date=date(2026, 5, 4), end_date=date(2026, 5, 10),
        status="approved",
    )
    assignments = [
        FakeAssignment("a1", "doc1", date(2026, 5, 5), "area1"),
        FakeAssignment("a2", "doc2", date(2026, 5, 6), "area2"),
    ]

    result = triggers.on_week_approved(
        actor_id="user1", assignments=assignments, week=week,
    )

    assert result == 2
    assert notif_service.queue.call_count == 2
    assert confirmation_service.create_request.call_count == 2
    notif_service.queue.assert_has_calls([
        call(
            notification_type="initial_assignment",
            idempotency_key="assign:a1",
            recipient_doctor_id="doc1",
            recipient_phone="+18095551234",
            payload=ANY,
            assignment_id="a1",
            created_by="user1",
        ),
        call(
            notification_type="initial_assignment",
            idempotency_key="assign:a2",
            recipient_doctor_id="doc2",
            recipient_phone="+18095554321",
            payload=ANY,
            assignment_id="a2",
            created_by="user1",
        ),
    ])


def test_on_week_approved_handles_missing_doctor():
    """Doctors not in the repo don't crash the loop."""
    notif_service = MagicMock()
    doctor_repo = FakeDoctorRepo()
    # doc1 is NOT in doctor_repo

    triggers = NotificationTriggers(
        notification_service=notif_service,
        doctor_repo=doctor_repo,
    )

    week = FakeWeek(
        id="week1", calendar_id="cal1", calendar_version_id="ver1",
        week_number=1, label="1RA SEMANA",
        start_date=date(2026, 5, 4), end_date=date(2026, 5, 10),
        status="approved",
    )
    # Should not crash; queues notification with phone=None (same as on_calendar_approved)
    result = triggers.on_week_approved(
        actor_id="user1",
        assignments=[FakeAssignment("a1", "doc1", date(2026, 5, 5), "area1")],
        week=week,
    )
    assert result == 1
    notif_service.queue.assert_called_once()
    call_kwargs = notif_service.queue.call_args.kwargs
    assert call_kwargs["recipient_phone"] is None
    assert call_kwargs["recipient_doctor_id"] == "doc1"
