from datetime import UTC, datetime, timedelta

from backend.app.application.action_alerts.service import ActionAlertService
from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository


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
