"""Una confirmación de un turno cancelado no puede seguir viva.

Si queda `pending`, el job de escalación la va a incluir y el encargado recibirá
un aviso por un turno que ya no existe.
"""

from datetime import UTC, datetime, timedelta

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.repositories.confirmations import (
    ConfirmationRequestRepository,
)
from backend.tests.notifications.test_triggers import _create_doctor, _make_assignment


def _request(
    session, doctor_id: str, *, key: str, status: str, assignment_id: str
) -> ConfirmationRequestModel:
    now = datetime.now(UTC)
    request = ConfirmationRequestModel(
        id=f"cr-{key}",
        confirmation_type="service",
        status=status,
        idempotency_key=key,
        response_token=f"tok-{key}",
        doctor_id=doctor_id,
        assignment_id=assignment_id,
        due_at=now + timedelta(hours=2),
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    session.flush()
    return request


def test_cancela_pendientes_y_recibidas(db_session):
    doctor = _create_doctor(db_session)
    a1 = _make_assignment(db_session, doctor_id=doctor.id)
    a2 = _make_assignment(db_session, doctor_id=doctor.id)
    a3 = _make_assignment(db_session, doctor_id=doctor.id)

    pendiente = _request(db_session, doctor.id, key="k1", status="pending", assignment_id=a1.id)
    recibida = _request(db_session, doctor.id, key="k2", status="received", assignment_id=a2.id)
    confirmada = _request(db_session, doctor.id, key="k3", status="confirmed", assignment_id=a3.id)

    ids = ConfirmationRequestRepository(db_session).cancel_pending_for_assignments(
        [a1.id, a2.id, a3.id]
    )

    assert set(ids) == {pendiente.id, recibida.id}
    for row in (pendiente, recibida, confirmada):
        db_session.refresh(row)
    assert pendiente.status == "cancelled"
    assert recibida.status == "cancelled"
    assert confirmada.status == "confirmed"


def test_el_servicio_expone_la_cancelacion(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    request = _request(
        db_session, doctor.id, key="k9", status="pending", assignment_id=assignment.id
    )

    service = ConfirmationRequestService(ConfirmationRequestRepository(db_session))

    assert service.cancel_for_assignments([assignment.id]) == [request.id]
