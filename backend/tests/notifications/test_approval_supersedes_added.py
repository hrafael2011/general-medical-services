"""Aprobar reemplaza el «te asignaron»: un solo mensaje por turno.

Al agregar un médico a una semana ya aprobada se encola un aviso
`service_assignment_added`. Si después se vuelve a aprobar, ese aviso sigue
pendiente y el médico recibe dos mensajes casi iguales por el mismo turno.
La aprobación los cancela y pone el definitivo.
"""

from datetime import UTC, datetime

from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import NotificationRepository

from .test_triggers import _create_doctor, _make_assignment


def _event(db_session, *, assignment, key_suffix, notification_type, status):
    now = datetime.now(UTC)
    event = NotificationEventModel(
        id=f"ev-{key_suffix}",
        notification_type=notification_type,
        idempotency_key=f"{key_suffix}:{assignment.id}",
        recipient_doctor_id=None,
        recipient_phone="123",
        payload={"message": "hola"},
        assignment_id=assignment.id,
        status=status,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(event)
    db_session.flush()
    return event


def test_cancela_el_aviso_de_asignacion_pendiente(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    added = _event(
        db_session,
        assignment=assignment,
        key_suffix="added",
        notification_type="service_assignment_added",
        status="pending",
    )

    ids = NotificationRepository(db_session).cancel_added_for_assignments([assignment.id])

    assert ids == ["ev-added"]
    db_session.refresh(added)
    assert added.status == "cancelled"


def test_no_toca_el_aviso_de_aprobacion_pendiente(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    initial = _event(
        db_session,
        assignment=assignment,
        key_suffix="assign",
        notification_type="initial_assignment",
        status="pending",
    )

    assert NotificationRepository(db_session).cancel_added_for_assignments(
        [assignment.id]
    ) == []
    db_session.refresh(initial)
    assert initial.status == "pending"


def test_no_toca_lo_ya_enviado(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    sent = _event(
        db_session,
        assignment=assignment,
        key_suffix="added",
        notification_type="service_assignment_added",
        status="sent",
    )

    assert NotificationRepository(db_session).cancel_added_for_assignments(
        [assignment.id]
    ) == []
    db_session.refresh(sent)
    assert sent.status == "sent"


def test_aprobar_la_semana_cancela_el_aviso_suelto_antes_de_encolar():
    from unittest.mock import MagicMock

    from backend.app.application.notifications.triggers import NotificationTriggers

    notifications = MagicMock()
    notifications.queue.return_value = MagicMock(id="ev", payload={})
    triggers = NotificationTriggers(
        notification_service=notifications,
        doctor_repo=MagicMock(),
        approval_grace_minutes=0,
    )
    triggers._resolve_area = MagicMock(return_value=("Emergencia", None))
    assignment = MagicMock(id="a1", doctor_id="d1", service_date="2026-05-05")

    triggers.on_week_approved(actor_id="u1", assignments=[assignment], week=MagicMock())

    notifications.cancel_added_for_assignments.assert_called_once_with(["a1"])

    # El aviso definitivo se encola después: cancelarlo dejaría al médico sin nada.
    cancel_order = notifications.method_calls.index(
        ("cancel_added_for_assignments", (["a1"],), {})
    )
    queue_order = next(
        i for i, call in enumerate(notifications.method_calls) if call[0] == "queue"
    )
    assert cancel_order < queue_order
