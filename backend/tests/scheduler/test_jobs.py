"""Tests for APScheduler job functions.

All tests use FakeProvider — no real WhatsApp messages are sent.

The job functions use lazy imports (imports inside function bodies), so
patches must target the source modules, not the jobs module.
"""

from datetime import UTC, datetime, timedelta, date
from unittest.mock import MagicMock, patch

import pytest


def _make_scalars_result(items):
    """Build a mock that mimics SQLAlchemy scalars() Result.

    SQLAlchemy's session.scalars() returns a Result with .all() and
    .first(). Plain lists don't have these, so we wrap in a mock.
    The job functions also use list(scalars(...)), so the mock must
    be iterable.
    """
    result_mock = MagicMock()
    result_mock.all.return_value = items
    result_mock.first.return_value = items[0] if items else None
    # Support list(scalars(...)) by making the mock iterable
    result_mock.__iter__.return_value = iter(items)
    return result_mock


class TestSendPreServiceReminders:
    """Tests for send_pre_service_reminders() job."""

    def make_assignment(self, doctor_id, service_area_id, service_date, service_start_hour=8):
        a = MagicMock()
        a.id = 99
        a.doctor_id = doctor_id
        a.service_area_id = service_area_id
        a.service_date = service_date
        a.service_start_at = datetime(
            service_date.year, service_date.month, service_date.day,
            service_start_hour, 0, 0, tzinfo=UTC,
        )
        return a

    def make_doctor(self, doctor_id, name, whatsapp_phone):
        d = MagicMock()
        d.id = doctor_id
        d.name = name
        d.whatsapp_phone = whatsapp_phone
        return d

    def make_area(self, area_id, display_name, start_hour=8):
        a = MagicMock()
        a.id = area_id
        a.display_name = display_name
        a.start_hour = start_hour
        return a

    def test_creates_reminder_notifications_in_reminder_window(self):
        """When a doctor has an assignment tomorrow within the 12h reminder
        window, a reminder_12h notification should be queued."""
        from backend.app.application.scheduler.jobs import send_pre_service_reminders

        tomorrow = date.today() + timedelta(days=1)
        start_hour = 8
        start_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, start_hour, 0, 0, tzinfo=UTC)
        reminder_time = start_dt - timedelta(hours=12)

        doctor = self.make_doctor("d1", "Dr. Test", "+18091234567")
        area = self.make_area("emergencia", "Emergencia", start_hour)
        assignment = self.make_assignment("d1", "emergencia", tomorrow, start_hour)

        mock_session = MagicMock()
        mock_session.scalars.return_value = _make_scalars_result([assignment])
        mock_session.get.side_effect = lambda model, pk: {
            "d1": doctor, "emergencia": area,
        }.get(pk)

        mock_svc = MagicMock()
        mock_notification = MagicMock()
        mock_notification.id = "notif-001"
        mock_svc.queue.return_value = mock_notification

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "backend.app.application.notifications.service.NotificationService",
            return_value=mock_svc,
        ), patch(
            "backend.app.infrastructure.repositories.notifications.NotificationRepository",
        ), patch(
            "datetime.datetime",
        ) as mock_dt_cls:
            mock_dt_cls.now.return_value = reminder_time

            result = send_pre_service_reminders()

        assert result["reminders_sent"] == 1
        mock_svc.queue.assert_called_once()
        call_kwargs = mock_svc.queue.call_args.kwargs
        assert call_kwargs["notification_type"] == "reminder_12h"
        assert call_kwargs["recipient_doctor_id"] == "d1"
        assert call_kwargs["assignment_id"] == 99

    def test_skips_doctor_without_whatsapp_phone(self):
        """Doctors without a whatsapp_phone should be skipped."""
        from backend.app.application.scheduler.jobs import send_pre_service_reminders

        tomorrow = date.today() + timedelta(days=1)
        start_hour = 8
        start_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, start_hour, 0, 0, tzinfo=UTC)
        reminder_time = start_dt - timedelta(hours=12)

        doctor = self.make_doctor("d1", "Dr. SinWhatsApp", None)
        area = self.make_area("emergencia", "Emergencia", start_hour)
        assignment = self.make_assignment("d1", "emergencia", tomorrow, start_hour)

        mock_session = MagicMock()
        mock_session.scalars.side_effect = [
            _make_scalars_result([assignment]),
            _make_scalars_result([]),
        ]
        mock_session.get.side_effect = lambda model, pk: {
            "d1": doctor, "emergencia": area,
        }.get(pk)

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "datetime.datetime",
        ) as mock_dt_cls:
            mock_dt_cls.now.return_value = reminder_time

            result = send_pre_service_reminders()

        assert result["reminders_sent"] == 0

    def test_skips_assignment_outside_reminder_window(self):
        """Assignments whose reminder window hasn't been reached should
        be skipped."""
        from backend.app.application.scheduler.jobs import send_pre_service_reminders

        tomorrow = date.today() + timedelta(days=1)
        start_hour = 8
        start_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, start_hour, 0, 0, tzinfo=UTC)
        outside_window = start_dt - timedelta(hours=14)

        doctor = self.make_doctor("d1", "Dr. Test", "+18091234567")
        area = self.make_area("emergencia", "Emergencia", start_hour)
        assignment = self.make_assignment("d1", "emergencia", tomorrow, start_hour)

        mock_session = MagicMock()
        mock_session.scalars.side_effect = [
            _make_scalars_result([assignment]),
            _make_scalars_result([]),
        ]
        mock_session.get.side_effect = lambda model, pk: {
            "d1": doctor, "emergencia": area,
        }.get(pk)

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "datetime.datetime",
        ) as mock_dt_cls:
            mock_dt_cls.now.return_value = outside_window

            result = send_pre_service_reminders()

        assert result["reminders_sent"] == 0


class TestCheckUnconfirmedEscalamiento:
    """Tests for check_unconfirmed_escalamiento() job."""

    def test_no_stale_confirmations_returns_zero(self):
        """When no confirmations are overdue, return escalations=0."""
        from backend.app.application.scheduler.jobs import check_unconfirmed_escalamiento

        mock_session = MagicMock()
        mock_session.scalars.return_value = _make_scalars_result([])

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ):
            result = check_unconfirmed_escalamiento()

        assert result["escalations"] == 0

    def test_finds_stale_confirmations_and_escalates(self):
        """When confirmations are >24h old and unconfirmed, escalate to
        encargados with receive_escalation_alerts permission."""
        from backend.app.application.scheduler.jobs import check_unconfirmed_escalamiento

        stale_req = MagicMock()
        stale_req.id = 1
        stale_req.doctor_id = "d1"
        stale_req.status = "pending"
        stale_req.assignment_id = 10

        encargado = MagicMock()
        encargado.id = "u1"
        encargado.whatsapp_phone = "+18091112222"

        doctor = MagicMock()
        doctor.id = "d1"
        doctor.name = "Dr. Unconfirmed"

        mock_session = MagicMock()
        mock_session.scalars.side_effect = [
            _make_scalars_result([stale_req]),
            _make_scalars_result([encargado]),
        ]
        mock_session.get.side_effect = lambda model, pk: {
            "d1": doctor,
        }.get(pk)

        mock_svc = MagicMock()

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "backend.app.application.notifications.service.NotificationService",
            return_value=mock_svc,
        ), patch(
            "backend.app.infrastructure.repositories.notifications.NotificationRepository",
        ), patch(
            "backend.app.infrastructure.repositories.doctors.DoctorRepository",
        ):
            result = check_unconfirmed_escalamiento()

        assert result["escalations"] == 1
        mock_svc.queue.assert_called_once()

    def test_no_encargados_with_permission_returns_zero(self):
        """When there are stale confirmations but no encargados with
        whatsapp_phone and receive_escalation_alerts, return 0."""
        from backend.app.application.scheduler.jobs import check_unconfirmed_escalamiento

        stale_req = MagicMock()
        stale_req.id = 1
        stale_req.doctor_id = "d1"

        mock_session = MagicMock()
        mock_session.scalars.side_effect = [
            _make_scalars_result([stale_req]),
            _make_scalars_result([]),
        ]

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ):
            result = check_unconfirmed_escalamiento()

        assert result["escalations"] == 0


class TestProcessOverdueConfirmations:
    """Tests for process_overdue_confirmations() job."""

    def test_processes_overdue_confirmations(self):
        """Calls ConfirmationRequestService.process_overdue() and
        returns the result."""
        from backend.app.application.scheduler.jobs import process_overdue_confirmations

        mock_session = MagicMock()
        mock_svc = MagicMock()
        mock_svc.process_overdue.return_value = {"expired": 3, "alerts_created": 2}

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "backend.app.application.confirmations.service.ConfirmationRequestService",
            return_value=mock_svc,
        ):
            result = process_overdue_confirmations()

        assert result == {"expired": 3, "alerts_created": 2}
        mock_svc.process_overdue.assert_called_once_with(actor_id=None)

    def test_handles_exception_gracefully(self):
        """When process_overdue raises, return zeros and don't crash."""
        from backend.app.application.scheduler.jobs import process_overdue_confirmations

        mock_session = MagicMock()
        mock_svc = MagicMock()
        mock_svc.process_overdue.side_effect = RuntimeError("DB down")

        with patch(
            "backend.app.infrastructure.db.session.SessionLocal",
            return_value=mock_session,
        ), patch(
            "backend.app.application.confirmations.service.ConfirmationRequestService",
            return_value=mock_svc,
        ):
            result = process_overdue_confirmations()

        assert result == {"expired": 0, "alerts_created": 0}
