"""Ver y cancelar el envío programado, sin desbloquear nada.

Es la mitad visible del margen de 15 minutos: el operador aprueba, ve cuándo
salen los avisos, y puede retirarlos si se equivocó sin deshacer la aprobación.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.models.calendars import CalendarVersionModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app
from backend.tests.notifications.test_triggers import _create_doctor, _make_assignment


@pytest.fixture
def user():
    return UserModel(
        id="test-user",
        email="user@test.com",
        password_hash="hash",
        name="Test User",
        role="admin",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def client(session_local, user):
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def calendar_with_pending(db_session):
    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    version = db_session.get(CalendarVersionModel, assignment.calendar_version_id)
    calendar_id = version.calendar_id

    now = datetime.now(UTC)
    for index in (1, 2):
        db_session.add(
            NotificationEventModel(
                id=f"pend-{index}",
                notification_type="initial_assignment",
                idempotency_key=f"assign:{assignment.id}:{index}",
                recipient_doctor_id=None,
                recipient_phone="123",
                payload={"message": "hola"},
                assignment_id=assignment.id,
                scheduled_for=now + timedelta(minutes=15),
                status="pending",
                retry_count=0,
                created_at=now,
                updated_at=now,
            )
        )
    db_session.commit()
    return calendar_id


def test_muestra_cuantos_avisos_estan_programados(client, calendar_with_pending):
    response = client.get(f"/api/calendars/{calendar_with_pending}/notifications/pending")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["next_send_at"] is not None


def test_cancela_el_envio_sin_desbloquear(client, calendar_with_pending):
    cancel = client.post(f"/api/calendars/{calendar_with_pending}/notifications/cancel")

    assert cancel.status_code == 200
    assert cancel.json()["cancelled"] == 2

    pendientes = client.get(
        f"/api/calendars/{calendar_with_pending}/notifications/pending"
    )
    assert pendientes.json()["count"] == 0


def test_calendario_sin_versiones_responde_404(client):
    response = client.get("/api/calendars/no-existe/notifications/pending")

    assert response.status_code == 404
