"""Cancelar avisos que todavía no han salido.

Regla del spec de aprobación segura: solo `pending`. Nunca `sending` (el worker
puede tenerlo en vuelo) ni `sent` (lo enviado no se recupera).
"""

from datetime import UTC, datetime

from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import NotificationRepository

from .test_triggers import _create_doctor, _make_assignment


def _event(session, *, assignment_id: str, status: str, suffix: str) -> NotificationEventModel:
    now = datetime.now(UTC)
    event = NotificationEventModel(
        id=f"ev-{suffix}",
        notification_type="initial_assignment",
        idempotency_key=f"assign:{suffix}",
        recipient_doctor_id=None,
        recipient_phone="123",
        payload={"message": "hola"},
        assignment_id=assignment_id,
        status=status,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    session.flush()
    return event


def test_cancela_solo_los_pendientes(db_session):
    doctor = _create_doctor(db_session)
    a1 = _make_assignment(db_session, doctor_id=doctor.id)
    a2 = _make_assignment(db_session, doctor_id=doctor.id)
    a3 = _make_assignment(db_session, doctor_id=doctor.id)

    pendiente = _event(db_session, assignment_id=a1.id, status="pending", suffix="1")
    enviado = _event(db_session, assignment_id=a2.id, status="sent", suffix="2")
    en_vuelo = _event(db_session, assignment_id=a3.id, status="sending", suffix="3")

    cancelados = NotificationRepository(db_session).cancel_pending_for_assignments(
        [a1.id, a2.id, a3.id]
    )

    assert cancelados == [pendiente.id]
    for row in (pendiente, enviado, en_vuelo):
        db_session.refresh(row)
    assert pendiente.status == "cancelled"
    assert enviado.status == "sent"
    assert en_vuelo.status == "sending"


def test_sin_asignaciones_no_consulta(db_session):
    """Desbloquear una semana vacía no debe recorrer la tabla."""
    assert NotificationRepository(db_session).cancel_pending_for_assignments([]) == []
