"""Tests for the notification bot webhook.

This route had none, which is how two defects survived: `/start <token>` was not handled
at all — so a system user could never be linked to the bot that actually sends — and a
doctor's confirmation created its notice for the encargado already marked `skipped`, so
nobody was ever told.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.telegram import TelegramLinkTokenModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app

SECRET = "test-webhook-secret"
ALERTS_PERMISSION = "receive_escalation_alerts"


@pytest.fixture
def client(session_local):
    app = create_app()

    def _get_session():
        session = session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = _get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _secret_and_no_outbound(monkeypatch):
    """Configure the webhook secret and stop replies from leaving the process."""
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "telegram_notification_bot_token", "token")
    monkeypatch.setattr(
        "backend.app.api.routes.telegram_notification_webhook._send_telegram_message",
        lambda *args, **kwargs: {"ok": True},
    )


def _post(client: TestClient, body: dict):
    return client.post(
        "/api/webhooks/telegram-notification",
        json=body,
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )


def _message(chat_id: str, text: str) -> dict:
    return {"message": {"chat": {"id": int(chat_id)}, "from": {"id": int(chat_id)}, "text": text}}


# ---------------------------------------------------------------------------
# A system user linking to the alerts bot
# ---------------------------------------------------------------------------


def _make_user(session, **kwargs) -> UserModel:
    user = UserModel(
        id=kwargs.get("id", "u1"),
        email=kwargs.get("email", "u1@test.com"),
        password_hash="hash",
        name=kwargs.get("name", "Encargada"),
        role=kwargs.get("role", "encargado"),
        active=True,
        must_change_password=False,
        token_version=1,
        permissions=kwargs.get("permissions", [ALERTS_PERMISSION]),
        telegram_chat_id=kwargs.get("telegram_chat_id"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _make_token(session, user: UserModel, **kwargs) -> TelegramLinkTokenModel:
    token = TelegramLinkTokenModel(
        id=kwargs.get("id", "t1"),
        token=kwargs.get("token", "tok-1"),
        user_id=user.id,
        created_by=None,
        created_at=datetime.now(UTC),
        expires_at=kwargs.get("expires_at", datetime.now(UTC) + timedelta(hours=1)),
        active=kwargs.get("active", True),
        used_at=kwargs.get("used_at"),
    )
    session.add(token)
    session.commit()
    return token


def test_start_with_a_token_links_the_user_to_the_alerts_bot(client, session):
    """The whole point: the chat id lands where the notification job reads it."""
    user = _make_user(session)
    _make_token(session, user)

    resp = _post(client, _message("555", "/start tok-1"))

    assert resp.status_code == 200
    session.refresh(user)
    assert user.telegram_chat_id == "555"


def test_a_link_token_cannot_be_used_twice(client, session):
    user = _make_user(session)
    _make_token(session, user, used_at=datetime.now(UTC))

    _post(client, _message("666", "/start tok-1"))

    session.refresh(user)
    assert user.telegram_chat_id is None


def test_an_expired_token_is_refused(client, session):
    user = _make_user(session)
    _make_token(session, user, expires_at=datetime.now(UTC) - timedelta(minutes=1))

    _post(client, _message("777", "/start tok-1"))

    session.refresh(user)
    assert user.telegram_chat_id is None


def test_a_chat_already_linked_to_another_account_is_refused(client, session):
    first = _make_user(session, id="u1", email="u1@test.com")
    first.telegram_chat_id = "888"
    second = _make_user(session, id="u2", email="u2@test.com")
    _make_token(session, second, id="t2", token="tok-2")
    session.commit()

    _post(client, _message("888", "/start tok-2"))

    session.refresh(second)
    assert second.telegram_chat_id is None


def test_a_plain_start_still_asks_a_doctor_for_their_phone(client, session):
    """No regression: the doctor flow must survive the new token branch."""
    resp = _post(client, _message("999", "/start"))

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# The receipt for the encargado when a doctor answers
# ---------------------------------------------------------------------------


def _make_doctor(session, *, chat_id: str = "123") -> DoctorModel:
    doctor = DoctorModel(
        id="doc-1",
        name="DRA. PRUEBA",
        normalized_name="dra prueba",
        sex="female",
        whatsapp_phone="8091234567",
        telegram_chat_id=chat_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(doctor)
    session.commit()
    return doctor


def _make_confirmation(session, doctor: DoctorModel) -> ConfirmationRequestModel:
    request = ConfirmationRequestModel(
        id="conf-1",
        confirmation_type="service",
        status="pending",
        idempotency_key="conf-key-1",
        response_token="resp-token-1",
        doctor_id=doctor.id,
        due_at=datetime.now(UTC) + timedelta(hours=12),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(request)
    session.commit()
    return request


def test_a_doctor_confirmation_queues_a_real_notice_for_the_encargado(client, session):
    """It used to be written with status="skipped" and no recipient: born dead."""
    doctor = _make_doctor(session)
    _make_confirmation(session, doctor)
    _make_user(session, telegram_chat_id="555")

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 123},
                "data": "confirm:conf-1",
                "message": {"message_id": 10, "chat": {"id": 123}},
            }
        },
    )

    events = session.query(NotificationEventModel).filter_by(
        notification_type="confirmation_receipt"
    ).all()
    assert len(events) == 1
    event = events[0]
    assert event.status == "pending", "el aviso nace listo para enviarse, no omitido"
    assert event.recipient_phone == "555"


def test_no_receipt_is_queued_for_a_user_without_telegram(client, session):
    """Someone who cannot receive must not produce a doomed event."""
    doctor = _make_doctor(session)
    _make_confirmation(session, doctor)
    _make_user(session, permissions=[])  # holds no alert permission

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 123},
                "data": "confirm:conf-1",
                "message": {"message_id": 10, "chat": {"id": 123}},
            }
        },
    )

    assert session.query(NotificationEventModel).filter_by(
        notification_type="confirmation_receipt"
    ).count() == 0
