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


# ---------------------------------------------------------------------------
# Un bloque por semana
# ---------------------------------------------------------------------------


def _week_row(db_session, *, version_id: str, calendar_id: str, number, start, end):
    from backend.app.infrastructure.db.models.calendars import CalendarWeekModel

    db_session.add(
        CalendarWeekModel(
            id=f"w-{number}",
            calendar_id=calendar_id,
            calendar_version_id=version_id,
            week_number=number,
            label=f"{number}TA SEMANA",
            start_date=start,
            end_date=end,
            status="approved",
        )
    )
    db_session.flush()


def _assignment_on(db_session, *, version_id: str, doctor_id: str, day, area_id: str):
    from datetime import datetime as _dt

    from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel

    assignment = CalendarAssignmentModel(
        id=f"a-{day.isoformat()}",
        calendar_version_id=version_id,
        service_date=day,
        service_area_id=area_id,
        doctor_id=doctor_id,
        created_at=_dt.now(UTC),
    )
    db_session.add(assignment)
    db_session.flush()
    return assignment


def _pending_event(db_session, *, assignment_id: str, sends_at):
    now = datetime.now(UTC)
    db_session.add(
        NotificationEventModel(
            id=f"ev-{assignment_id}",
            notification_type="initial_assignment",
            idempotency_key=f"assign:{assignment_id}",
            recipient_doctor_id=None,
            recipient_phone="123",
            payload={"message": "hola"},
            assignment_id=assignment_id,
            scheduled_for=sends_at,
            status="pending",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()


@pytest.fixture
def calendar_with_two_weeks(db_session):
    """Dos semanas aprobadas con horas de envío distintas."""
    from datetime import date

    doctor = _create_doctor(db_session)
    first = _make_assignment(db_session, doctor_id=doctor.id)
    version = db_session.get(CalendarVersionModel, first.calendar_version_id)
    calendar_id = version.calendar_id
    area_id = first.service_area_id

    _week_row(
        db_session,
        version_id=version.id,
        calendar_id=calendar_id,
        number=1,
        start=date(2026, 5, 4),
        end=date(2026, 5, 10),
    )
    _week_row(
        db_session,
        version_id=version.id,
        calendar_id=calendar_id,
        number=2,
        start=date(2026, 5, 11),
        end=date(2026, 5, 17),
    )

    week1 = _assignment_on(
        db_session, version_id=version.id, doctor_id=doctor.id,
        day=date(2026, 5, 5), area_id=area_id,
    )
    week2 = _assignment_on(
        db_session, version_id=version.id, doctor_id=doctor.id,
        day=date(2026, 5, 12), area_id=area_id,
    )

    now = datetime.now(UTC)
    _pending_event(db_session, assignment_id=week1.id, sends_at=now + timedelta(hours=3))
    _pending_event(db_session, assignment_id=week2.id, sends_at=now + timedelta(hours=15))
    db_session.commit()
    return calendar_id


def test_agrupa_los_avisos_por_semana(client, calendar_with_two_weeks):
    response = client.get(
        f"/api/calendars/{calendar_with_two_weeks}/notifications/pending"
    )

    assert response.status_code == 200
    groups = response.json()["groups"]
    assert [g["week_label"] for g in groups] == ["1TA SEMANA", "2TA SEMANA"]
    assert [g["count"] for g in groups] == [1, 1]
    # El primero que sale va primero
    assert groups[0]["next_send_at"] < groups[1]["next_send_at"]


def test_el_total_es_la_suma_de_los_grupos(client, calendar_with_two_weeks):
    body = client.get(
        f"/api/calendars/{calendar_with_two_weeks}/notifications/pending"
    ).json()

    assert body["count"] == sum(g["count"] for g in body["groups"])


def test_cancelar_una_semana_deja_la_otra(client, calendar_with_two_weeks):
    cancel = client.post(
        f"/api/calendars/{calendar_with_two_weeks}/notifications/cancel",
        json={"week_id": "w-2"},
    )

    assert cancel.status_code == 200
    assert cancel.json()["cancelled"] == 1

    body = client.get(
        f"/api/calendars/{calendar_with_two_weeks}/notifications/pending"
    ).json()
    assert [g["week_label"] for g in body["groups"]] == ["1TA SEMANA"]
