"""Re-aprobar tras desbloquear debe volver a avisar.

Antes, `approve_calendar` callaba todas las notificaciones cuando veía un
`__unlock__` en el motivo. Resultado: quien había aprobado por error, desbloqueado
y corregido, dejaba a los médicos sin enterarse de la versión buena.

La fila cancelada se **reutiliza** en vez de crear otra: la clave de idempotencia
por asignación sigue siendo la misma, así que no hay avisos duplicados.
"""

from datetime import UTC, datetime

from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.confirmations import (
    ConfirmationRequestRepository,
)
from backend.app.infrastructure.repositories.notifications import NotificationRepository

from .test_triggers import _create_doctor, _make_assignment


def test_reactiva_los_avisos_cancelados(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    now = datetime.now(UTC)
    event = NotificationEventModel(
        id="ev-reactivar",
        notification_type="initial_assignment",
        idempotency_key=f"assign:{assignment.id}",
        recipient_doctor_id=None,
        recipient_phone="123",
        payload={"message": "hola"},
        assignment_id=assignment.id,
        status="cancelled",
        retry_count=2,
        created_at=now,
        updated_at=now,
    )
    db_session.add(event)
    db_session.flush()

    ids = NotificationRepository(db_session).reactivate_cancelled_for_assignments(
        [assignment.id]
    )

    assert ids == ["ev-reactivar"]
    db_session.refresh(event)
    assert event.status == "pending"
    assert event.retry_count == 0


def test_no_toca_lo_ya_enviado(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    now = datetime.now(UTC)
    enviado = NotificationEventModel(
        id="ev-enviado",
        notification_type="initial_assignment",
        idempotency_key=f"assign:{assignment.id}",
        recipient_doctor_id=None,
        recipient_phone="123",
        payload={"message": "hola"},
        assignment_id=assignment.id,
        status="sent",
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(enviado)
    db_session.flush()

    assert NotificationRepository(db_session).reactivate_cancelled_for_assignments(
        [assignment.id]
    ) == []
    db_session.refresh(enviado)
    assert enviado.status == "sent"


def test_reactiva_la_confirmacion_cancelada(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    now = datetime.now(UTC)
    request = ConfirmationRequestModel(
        id="cr-reactivar",
        confirmation_type="service",
        status="cancelled",
        idempotency_key=f"service:{assignment.id}:{doctor.id}",
        response_token="tok-reactivar",
        doctor_id=doctor.id,
        assignment_id=assignment.id,
        escalated_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(request)
    db_session.flush()

    ids = ConfirmationRequestRepository(db_session).reactivate_for_assignments([assignment.id])

    assert ids == ["cr-reactivar"]
    db_session.refresh(request)
    assert request.status == "pending"
    assert request.escalated_at is None


def test_no_reactiva_una_confirmacion_ya_respondida(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    now = datetime.now(UTC)
    request = ConfirmationRequestModel(
        id="cr-confirmada",
        confirmation_type="service",
        status="confirmed",
        idempotency_key=f"service:{assignment.id}:{doctor.id}",
        response_token="tok-confirmada",
        doctor_id=doctor.id,
        assignment_id=assignment.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(request)
    db_session.flush()

    assert ConfirmationRequestRepository(db_session).reactivate_for_assignments(
        [assignment.id]
    ) == []
