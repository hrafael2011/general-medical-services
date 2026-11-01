"""Deshacer la aprobación debe deshacer el aviso.

`on_week_unapproved` es el espejo de `on_week_approved`: cancela lo que aquel
encoló y que todavía no ha salido.
"""

from unittest.mock import MagicMock

from backend.app.application.notifications.triggers import NotificationTriggers


def test_on_week_unapproved_cancela_avisos_y_confirmaciones():
    notifications = MagicMock()
    notifications.cancel_for_assignments.return_value = ["ev1", "ev2"]
    confirmations = MagicMock()
    confirmations.cancel_for_assignments.return_value = ["cr1"]

    triggers = NotificationTriggers(
        notification_service=notifications,
        doctor_repo=MagicMock(),
        confirmation_service=confirmations,
    )
    a1, a2 = MagicMock(id="a1"), MagicMock(id="a2")

    result = triggers.on_week_unapproved(actor_id="user1", assignments=[a1, a2])

    notifications.cancel_for_assignments.assert_called_once_with(["a1", "a2"])
    confirmations.cancel_for_assignments.assert_called_once_with(["a1", "a2"])
    assert result == {"notifications": 2, "confirmations": 1}


def test_on_week_unapproved_sin_servicio_de_confirmaciones():
    """Sin servicio de confirmaciones solo se cancelan los avisos."""
    notifications = MagicMock()
    notifications.cancel_for_assignments.return_value = ["ev1"]

    triggers = NotificationTriggers(
        notification_service=notifications,
        doctor_repo=MagicMock(),
    )

    result = triggers.on_week_unapproved(actor_id="user1", assignments=[MagicMock(id="a1")])

    assert result == {"notifications": 1, "confirmations": 0}


def test_quitar_un_turno_cancela_su_confirmacion():
    """Sin esto la confirmación sigue viva y escala por un turno que no existe."""
    confirmations = MagicMock()
    confirmations.cancel_for_assignments.return_value = ["cr1"]
    triggers = NotificationTriggers(
        notification_service=MagicMock(),
        doctor_repo=MagicMock(),
        confirmation_service=confirmations,
    )
    triggers._queue_service_change = MagicMock(return_value=1)
    assignment = MagicMock(id="a1", doctor_id="doc1", service_date="2026-05-05")

    triggers.on_calendar_assignment_removed_after_approval(
        actor_id="user1", assignment=assignment, service_area_name="Emergencia"
    )

    confirmations.cancel_for_assignments.assert_called_once_with(["a1"])
    # El aviso de "removido" se encola igual: el médico tiene que enterarse.
    triggers._queue_service_change.assert_called_once()
