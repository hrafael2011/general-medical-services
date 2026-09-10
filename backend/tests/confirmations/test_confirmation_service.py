from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.missions import MissionAssignmentModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository


@pytest.fixture(autouse=True)
def seeded(db_session) -> None:
    """Sembrado de las entidades que los tests referencian por FK.

    PostgreSQL valida las foreign keys (SQLite no): cada id que aparece en un
    create_request (`doctor_id`, `assignment_id`, `notification_id`,
    `mission_id`, `created_by`) debe existir de verdad en la base.
    """
    now = datetime.now(UTC)

    doctor = DoctorModel(
        id="doctor-1",
        name="Doctor Semilla",
        normalized_name="doctor semilla",
        sex="male",
        rank_id=None,
        department_id=None,
        notes=None,
        active=True,
        service_active=True,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        whatsapp_phone="+18095551234",
        monthly_service_target=3,
        monthly_service_max=6,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_by="actor-1",
        created_at=now,
        updated_at=now,
        deactivated_at=None,
        deactivated_by=None,
    )
    db_session.add(doctor)
    # SQLAlchemy ordena los INSERT por relationship(), no por ForeignKey suelto:
    # sin este flush insertaría las hijas antes que el doctor y PostgreSQL
    # rechazaría la FK (SQLite no la validaba y lo tapaba).
    db_session.flush()

    db_session.add(
        UserModel(
            id="actor-1",
            name="Actor Semilla",
            email="actor-1@example.com",
            role="admin",
            permissions=[],
            is_superadmin=False,
            active=True,
            password_hash="hash",
            must_change_password=False,
            token_version=1,
            failed_login_count=0,
            locked_until=None,
            last_login_at=None,
            password_changed_at=None,
            created_by=None,
            created_at=now,
            updated_at=now,
            deactivated_at=None,
            deactivated_by=None,
            deleted_at=None,
            whatsapp_phone=None,
            telegram_chat_id=None,
        )
    )
    db_session.flush()

    calendar = CalendarModel(
        id=str(uuid4()),
        year=2026,
        month=5,
        status="approved",
        created_by="actor-1",
        approved_by="actor-1",
        created_at=now,
        updated_at=now,
        approved_at=now,
    )
    db_session.add(calendar)
    db_session.flush()

    version = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=1,
        status="approved",
        created_by="actor-1",
        reason=None,
        created_at=now,
        approved_at=now,
        approved_by="actor-1",
    )
    db_session.add(version)
    db_session.flush()

    area = ServiceAreaModel(
        id=str(uuid4()),
        code="semilla",
        display_name="Área Semilla",
        active=True,
        required_for_daily_coverage=True,
        load_weight=1,
        start_hour=7,
        created_at=now,
        updated_at=now,
    )
    db_session.add(area)
    db_session.flush()

    # Fechas distintas: hay unique constraint sobre
    # (calendar_version_id, service_date, service_area_id).
    for assignment_id, service_date in (
        ("assignment-1", date(2026, 5, 20)),
        ("assignment-2", date(2026, 5, 21)),
    ):
        db_session.add(
            CalendarAssignmentModel(
                id=assignment_id,
                calendar_version_id=version.id,
                service_date=service_date,
                service_start_at=None,
                service_area_id=area.id,
                doctor_id=doctor.id,
                assignment_source="manual",
                rationale=None,
                override_justification=None,
                created_by="actor-1",
                created_at=now,
            )
        )
    db_session.flush()

    db_session.add(
        MissionAssignmentModel(
            id="mission-1",
            mission_date=date(2026, 5, 20),
            mission_start_at=None,
            mission_end_at=None,
            participant_count=2,
            location=None,
            description=None,
            source="manual",
            status="draft",
            created_by="actor-1",
            confirmed_by=None,
            confirmed_at=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db_session.flush()

    db_session.add(
        NotificationEventModel(
            id="notification-1",
            notification_type="mission_participant",
            recipient_doctor_id=doctor.id,
            recipient_phone=None,
            assignment_id=None,
            mission_id=None,
            idempotency_key="notification-seed-1",
            scheduled_for=None,
            sent_at=None,
            last_retried_at=None,
            status="pending",
            provider=None,
            provider_message_id=None,
            error_code=None,
            error_message=None,
            retry_count=0,
            payload=None,
            created_by="actor-1",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()


def _make_service(db_session) -> ConfirmationRequestService:
    return ConfirmationRequestService(ConfirmationRequestRepository(db_session))


def _make_alerting_service(db_session) -> ConfirmationRequestService:
    return ConfirmationRequestService(
        ConfirmationRequestRepository(db_session),
        action_alerts=ActionAlertService(ActionAlertRepository(db_session)),
    )


def test_create_request_is_pending_and_idempotent(db_session) -> None:
    service = _make_service(db_session)

    first = service.create_request(
        confirmation_type="service",
        idempotency_key="service:assignment-1:doctor-1",
        doctor_id="doctor-1",
        assignment_id="assignment-1",
        notification_id="notification-1",
        created_by="actor-1",
    )
    second = service.create_request(
        confirmation_type="service",
        idempotency_key="service:assignment-1:doctor-1",
        doctor_id="doctor-1",
        assignment_id="assignment-1",
        notification_id="notification-1",
        created_by="actor-1",
    )

    assert first.id == second.id
    assert first.status == "pending"
    assert first.confirmation_type == "service"
    assert first.response_token
    assert first.response_token == second.response_token


def test_mark_confirmed_records_response(db_session) -> None:
    service = _make_service(db_session)
    request = service.create_request(
        confirmation_type="mission",
        idempotency_key="mission:mission-1:doctor-1",
        doctor_id="doctor-1",
        mission_id="mission-1",
    )

    confirmed = service.mark_confirmed(
        request.id,
        response_channel="telegram",
        response_payload={"text": "Confirmo misión"},
    )

    assert confirmed.status == "confirmed"
    assert confirmed.responded_at is not None
    assert confirmed.response_channel == "telegram"
    assert confirmed.response_payload == {"text": "Confirmo misión"}


def test_mark_confirmed_by_token(db_session) -> None:
    service = _make_service(db_session)
    request = service.create_request(
        confirmation_type="service",
        idempotency_key="service:assignment-2:doctor-1",
        doctor_id="doctor-1",
        assignment_id="assignment-2",
    )

    confirmed = service.mark_confirmed_by_token(
        request.response_token,
        response_channel="telegram",
        response_payload={"text": "/confirmar token"},
    )

    assert confirmed.id == request.id
    assert confirmed.status == "confirmed"


def test_process_overdue_expires_pending_and_creates_alert(db_session) -> None:
    service = _make_alerting_service(db_session)
    due_at = datetime.now(UTC) - timedelta(minutes=1)
    request = service.create_request(
        confirmation_type="mission",
        idempotency_key="mission:overdue:doctor-1",
        doctor_id="doctor-1",
        mission_id="mission-1",
        due_at=due_at,
    )

    result = service.process_overdue(actor_id="actor-1")

    refreshed = ConfirmationRequestRepository(db_session).get_by_id(request.id)
    alerts = ActionAlertRepository(db_session).list_all(status="open", section="missions")
    assert result == {"expired": 1, "alerts_created": 1}
    assert refreshed is not None
    assert refreshed.status == "expired"
    assert len(alerts) == 1
    assert alerts[0].alert_type == "mission_confirmation_overdue"
    assert alerts[0].entity_id == request.id


def test_process_overdue_does_not_duplicate_alerts(db_session) -> None:
    service = _make_alerting_service(db_session)
    service.create_request(
        confirmation_type="service",
        idempotency_key="service:overdue:doctor-1",
        doctor_id="doctor-1",
        assignment_id="assignment-1",
        due_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    first = service.process_overdue(actor_id="actor-1")
    second = service.process_overdue(actor_id="actor-1")

    alerts = ActionAlertRepository(db_session).list_all(status="open", section="calendar")
    assert first == {"expired": 1, "alerts_created": 1}
    assert second == {"expired": 0, "alerts_created": 0}
    assert len(alerts) == 1


def test_confirming_expired_request_resolves_overdue_alert(db_session) -> None:
    service = _make_alerting_service(db_session)
    request = service.create_request(
        confirmation_type="mission",
        idempotency_key="mission:late-confirmation:doctor-1",
        doctor_id="doctor-1",
        mission_id="mission-1",
        due_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service.process_overdue(actor_id="actor-1")

    service.mark_confirmed_by_token(
        request.response_token,
        response_channel="telegram",
        response_payload={"user_id": "actor-1"},
    )

    open_alerts = ActionAlertRepository(db_session).list_all(status="open", section="missions")
    resolved_alerts = ActionAlertRepository(db_session).list_all(
        status="resolved",
        section="missions",
    )
    assert open_alerts == []
    assert len(resolved_alerts) == 1
    assert resolved_alerts[0].entity_id == request.id


def test_declined_request_creates_action_alert(db_session) -> None:
    service = _make_alerting_service(db_session)
    request = service.create_request(
        confirmation_type="service",
        idempotency_key="service:declined:doctor-1",
        doctor_id="doctor-1",
        assignment_id="assignment-1",
    )

    service.mark_declined_by_token(
        request.response_token,
        response_channel="telegram",
        response_payload={"user_id": "actor-1"},
    )

    alerts = ActionAlertRepository(db_session).list_all(status="open", section="calendar")
    assert len(alerts) == 1
    assert alerts[0].alert_type == "service_confirmation_declined"
    assert alerts[0].entity_id == request.id


# ---------------------------------------------------------------------------
# La transacción es de la RUTA, no del servicio
# ---------------------------------------------------------------------------


def _staged_notification(db_session, key: str) -> NotificationEventModel:
    """Trabajo que la ruta ya escenificó antes de crear la confirmación."""
    now = datetime.now(UTC)
    notification = NotificationEventModel(
        id=str(uuid4()),
        notification_type="initial_assignment",
        idempotency_key=key,
        status="pending",
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(notification)
    db_session.flush()
    return notification


def test_integrity_error_does_not_roll_back_the_callers_transaction(db_session) -> None:
    """Un IntegrityError al insertar la confirmación no puede tirar todo.

    La arquitectura es Route → Service → Repository (flush) → Route (commit):
    la transacción es de la RUTA. `create_request` hacía `session.rollback()`
    ante un IntegrityError y eso revertía TODO lo que la ruta ya había
    escenificado — la aprobación de la semana, las notificaciones anteriores —
    y la ruta igual respondía 200. El fallo era mudo: nada visible fallaba,
    simplemente no se guardaba. Con un SAVEPOINT sólo se deshace el INSERT.
    """
    staged = _staged_notification(db_session, f"propia:{uuid4()}")
    service = _make_service(db_session)

    with pytest.raises(IntegrityError):
        # doctor inexistente → violación de FK → IntegrityError, y el
        # get_by_idempotency_key de rescate tampoco encuentra nada.
        service.create_request(
            confirmation_type="service",
            idempotency_key=f"service:{uuid4()}",
            doctor_id="doctor-que-no-existe",
        )

    assert staged in db_session, "el servicio revirtió trabajo que no era suyo"
    db_session.execute(text("SELECT 1"))  # la transacción quedó usable


def test_idempotent_hit_does_not_touch_the_callers_transaction(db_session) -> None:
    """El atajo por idempotencia devuelve la existente sin tocar la transacción."""
    service = _make_service(db_session)
    key = f"service:{uuid4()}"
    first = service.create_request(
        confirmation_type="service", idempotency_key=key, doctor_id="doctor-1"
    )
    db_session.flush()

    staged = _staged_notification(db_session, f"propia:{uuid4()}")
    again = service.create_request(
        confirmation_type="service", idempotency_key=key, doctor_id="doctor-1"
    )

    assert again.id == first.id
    assert staged in db_session
