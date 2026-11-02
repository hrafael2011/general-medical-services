"""Aprobar no debe enviar en el acto: deja el aviso programado.

El margen existe para que un clic equivocado se pueda deshacer antes de que el
médico reciba nada.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from backend.app.application.notifications.triggers import NotificationTriggers


def _triggers(grace: int) -> tuple[NotificationTriggers, MagicMock]:
    notifications = MagicMock()
    notifications.queue.return_value = MagicMock(id="ev1", payload={})
    triggers = NotificationTriggers(
        notification_service=notifications,
        doctor_repo=MagicMock(),
        approval_grace_minutes=grace,
    )
    triggers._resolve_area = MagicMock(return_value=("Emergencia", None))
    return triggers, notifications


def test_on_week_approved_programa_el_envio():
    triggers, notifications = _triggers(grace=15)
    assignment = MagicMock(id="a1", doctor_id="doc1", service_date="2026-05-05")

    antes = datetime.now(UTC)
    triggers.on_week_approved(actor_id="user1", assignments=[assignment], week=MagicMock())

    programado = notifications.queue.call_args.kwargs["scheduled_for"]
    assert antes + timedelta(minutes=14) < programado < antes + timedelta(minutes=16)


def test_on_calendar_approved_programa_el_envio():
    triggers, notifications = _triggers(grace=15)
    assignment = MagicMock(id="a1", doctor_id="doc1", service_date="2026-05-05")

    triggers.on_calendar_approved(actor_id="user1", assignments=[assignment])

    programado = notifications.queue.call_args.kwargs["scheduled_for"]
    assert programado > datetime.now(UTC) + timedelta(minutes=14)


def test_sin_margen_envia_de_inmediato():
    """Los scripts y las pruebas no deben quedarse esperando 15 minutos."""
    triggers, notifications = _triggers(grace=0)
    assignment = MagicMock(id="a1", doctor_id="doc1", service_date="2026-05-05")

    triggers.on_calendar_approved(actor_id="user1", assignments=[assignment])

    assert notifications.queue.call_args.kwargs["scheduled_for"] is None


def test_la_ventana_por_defecto_es_de_24_horas():
    """Se aprueba el viernes para el lunes: 24 h cubren el fin de semana."""
    from backend.app.core.config import Settings

    assert Settings().approval_grace_minutes == 24 * 60
