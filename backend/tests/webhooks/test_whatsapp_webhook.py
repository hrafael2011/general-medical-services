"""Tests for WhatsApp webhook endpoints.

All tests use FastAPI TestClient with in-memory SQLite — no real Meta
webhook calls or WhatsApp messages are sent.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.infrastructure.db.models.catalogs import DepartmentModel, RankModel
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app
from backend.app.core.config import settings


@pytest.fixture(scope="function")
def db_session():
    """In-memory SQLite session with only webhook-relevant tables.

    UserModel (JSONB permissions column) is excluded because SQLite
    doesn't support the PostgreSQL JSONB type.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Manually create only tables the webhook needs (skip UserModel — JSONB
    # is unsupported in SQLite).
    DoctorModel.__table__.create(engine, checkfirst=True)
    NotificationEventModel.__table__.create(engine, checkfirst=True)
    ConfirmationRequestModel.__table__.create(engine, checkfirst=True)
    RankModel.__table__.create(engine, checkfirst=True)
    DepartmentModel.__table__.create(engine, checkfirst=True)

    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    with SessionLocal() as session:
        yield session

    engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient with DB dependency overridden."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


# ── GET verification ────────────────────────────────────────────────────────

class TestWebhookVerification:
    """Test GET /api/webhooks/whatsapp (Meta webhook verification)."""

    def test_valid_token_returns_challenge(self, client):
        """GET with correct mode=subscribe and matching verify_token
        returns the hub.challenge value."""
        original = settings.meta_webhook_verify_token
        settings.meta_webhook_verify_token = "secret-token"

        try:
            response = client.get(
                "/api/webhooks/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "secret-token",
                    "hub.challenge": "abc123",
                },
            )
            assert response.status_code == 200
            assert "abc123" in response.text
        finally:
            settings.meta_webhook_verify_token = original

    def test_invalid_token_returns_403(self, client):
        """GET with wrong verify_token returns 403."""
        original = settings.meta_webhook_verify_token
        settings.meta_webhook_verify_token = "secret-token"

        try:
            response = client.get(
                "/api/webhooks/whatsapp",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong-token",
                    "hub.challenge": "abc123",
                },
            )
            assert response.status_code == 403
        finally:
            settings.meta_webhook_verify_token = original

    def test_wrong_mode_returns_403(self, client):
        """GET with mode other than 'subscribe' returns 403 even
        with correct token."""
        original = settings.meta_webhook_verify_token
        settings.meta_webhook_verify_token = "secret-token"

        try:
            response = client.get(
                "/api/webhooks/whatsapp",
                params={
                    "hub.mode": "not-subscribe",
                    "hub.verify_token": "secret-token",
                    "hub.challenge": "abc123",
                },
            )
            assert response.status_code == 403
        finally:
            settings.meta_webhook_verify_token = original


# ── POST message reception ──────────────────────────────────────────────────

def _make_whatsapp_payload(sender_phone: str, text_body: str | None = "1",
                           msg_id: str = "wamid.test123") -> dict:
    """Build a minimal Meta Cloud API webhook payload."""
    messages = []
    if text_body is not None:
        messages.append({
            "from": sender_phone,
            "id": msg_id,
            "timestamp": "1717000000",
            "text": {"body": text_body},
            "type": "text",
        })
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15550987654",
                        "phone_number_id": "987654321",
                    },
                    "contacts": [{
                        "profile": {"name": "Test Doctor"},
                        "wa_id": sender_phone,
                    }],
                    "messages": messages,
                },
                "field": "messages",
            }],
        }],
    }


class TestWebhookReceive:
    """Test POST /api/webhooks/whatsapp (incoming message)."""

    def test_empty_entry_returns_200(self, client):
        """POST with an empty entry returns 200 OK."""
        payload = {"object": "whatsapp_business_account", "entry": []}
        response = client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_no_messages_returns_200(self, client):
        """POST with a valid structure but no messages returns 200."""
        payload = _make_whatsapp_payload("18091234567", text_body=None)
        response = client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_unexpected_json_returns_200(self, client):
        """POST with unexpected JSON structure returns 200 (webhooks
        should never return errors to Meta — they retry on non-200)."""
        payload = {"unexpected": "structure"}
        response = client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_reply_1_confirms_pending_request(self, client, db_session):
        """POST with body '1' from a known doctor's phone confirms the
        most recent pending ConfirmationRequest."""
        db_session.query(ConfirmationRequestModel).delete()
        db_session.query(NotificationEventModel).delete()
        db_session.query(DoctorModel).delete()
        db_session.commit()

        now = datetime.now(UTC)
        doctor = DoctorModel(
            id="doc-w1",
            name="Dr. Webhook",
            normalized_name="dr webhook",
            whatsapp_phone="18091234567",
            sex="M",
            active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(doctor)
        db_session.commit()

        now = datetime.now(UTC)
        notif = NotificationEventModel(
            id=str(uuid4()),
            notification_type="initial_assignment",
            recipient_phone="18091234567",
            recipient_doctor_id=doctor.id,
            idempotency_key="test:webhook:1",
            payload={"message": "Test"},
            status="pending",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        db_session.add(notif)
        db_session.commit()

        req = ConfirmationRequestModel(
            id=str(uuid4()),
            confirmation_type="service",
            status="pending",
            idempotency_key=f"test:webhook:{uuid4()}",
            response_token=str(uuid4()),
            doctor_id=doctor.id,
            notification_id=notif.id,
            due_at=now + timedelta(hours=48),
            created_at=now,
            updated_at=now,
        )
        db_session.add(req)
        db_session.commit()

        payload = _make_whatsapp_payload("18091234567", text_body="1")
        response = client.post("/api/webhooks/whatsapp", json=payload)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        db_session.refresh(req)
        assert req.status == "confirmed"
        assert req.responded_at is not None
        assert req.response_channel == "whatsapp"
        assert req.response_payload["reply"] == "1"

    def test_reply_non_1_does_not_confirm(self, client, db_session):
        """POST with text other than '1' does not change any
        confirmation status."""
        db_session.query(ConfirmationRequestModel).delete()
        db_session.query(NotificationEventModel).delete()
        db_session.query(DoctorModel).delete()
        db_session.commit()

        now2 = datetime.now(UTC)
        doctor = DoctorModel(
            id="doc-w2",
            name="Dr. Ignore",
            normalized_name="dr ignore",
            whatsapp_phone="18099998888",
            sex="M",
            active=True,
            created_at=now2,
            updated_at=now2,
        )
        db_session.add(doctor)
        db_session.commit()

        now = datetime.now(UTC)
        notif = NotificationEventModel(
            id=str(uuid4()),
            notification_type="initial_assignment",
            recipient_phone="18099998888",
            recipient_doctor_id=doctor.id,
            idempotency_key="test:webhook:2",
            payload={"message": "Test"},
            status="pending",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        db_session.add(notif)
        db_session.commit()

        req = ConfirmationRequestModel(
            id=str(uuid4()),
            confirmation_type="service",
            status="pending",
            idempotency_key=f"test:webhook:{uuid4()}",
            response_token=str(uuid4()),
            doctor_id=doctor.id,
            notification_id=notif.id,
            due_at=now + timedelta(hours=48),
            created_at=now,
            updated_at=now,
        )
        db_session.add(req)
        db_session.commit()

        payload = _make_whatsapp_payload("18099998888", text_body="Hola doctor")
        response = client.post("/api/webhooks/whatsapp", json=payload)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        db_session.refresh(req)
        assert req.status == "pending"

    def test_reply_from_unknown_phone_returns_200(self, client):
        """POST with '1' from an unknown phone number returns 200."""
        payload = _make_whatsapp_payload("18090000000", text_body="1")
        response = client.post("/api/webhooks/whatsapp", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_reply_with_spaces_in_1_confirms(self, client, db_session):
        """' 1 ' with spaces should also confirm (uses .strip())."""
        db_session.query(ConfirmationRequestModel).delete()
        db_session.query(NotificationEventModel).delete()
        db_session.query(DoctorModel).delete()
        db_session.commit()

        now3 = datetime.now(UTC)
        doctor = DoctorModel(
            id="doc-w3",
            name="Dr. Spaces",
            normalized_name="dr spaces",
            whatsapp_phone="18095556666",
            sex="M",
            active=True,
            created_at=now3,
            updated_at=now3,
        )
        db_session.add(doctor)
        db_session.commit()

        now = datetime.now(UTC)
        notif = NotificationEventModel(
            id=str(uuid4()),
            notification_type="initial_assignment",
            recipient_phone="18095556666",
            recipient_doctor_id=doctor.id,
            idempotency_key="test:webhook:3",
            payload={"message": "Test"},
            status="pending",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        db_session.add(notif)
        db_session.commit()

        req = ConfirmationRequestModel(
            id=str(uuid4()),
            confirmation_type="service",
            status="pending",
            idempotency_key=f"test:webhook:{uuid4()}",
            response_token=str(uuid4()),
            doctor_id=doctor.id,
            notification_id=notif.id,
            due_at=now + timedelta(hours=48),
            created_at=now,
            updated_at=now,
        )
        db_session.add(req)
        db_session.commit()

        payload = _make_whatsapp_payload("18095556666", text_body=" 1 ")
        response = client.post("/api/webhooks/whatsapp", json=payload)

        assert response.status_code == 200
        db_session.refresh(req)
        assert req.status == "confirmed"
