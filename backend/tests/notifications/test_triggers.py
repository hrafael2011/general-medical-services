"""
DB-backed integration tests for NotificationTriggers.

Uses the in-memory SQLite db_session fixture from conftest.py.
Doctors are created as real ORM rows; mission/assignment objects are faked
with types.SimpleNamespace so no additional DB setup is required for those.
"""

import datetime
import types
import uuid

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.application.notifications.providers import FakeProvider
from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.triggers import NotificationTriggers
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.notifications import NotificationRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACTOR = "actor-test"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_triggers(db_session) -> NotificationTriggers:
    return NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(db_session),
            provider=FakeProvider(),
        ),
        doctor_repo=DoctorRepository(db_session),
    )


def _make_confirming_triggers(db_session) -> NotificationTriggers:
    return NotificationTriggers(
        notification_service=NotificationService(
            repo=NotificationRepository(db_session),
            provider=FakeProvider(),
        ),
        doctor_repo=DoctorRepository(db_session),
        confirmation_service=ConfirmationRequestService(
            ConfirmationRequestRepository(db_session),
        ),
    )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _create_doctor(
    db_session,
    *,
    doctor_id: str | None = None,
    name: str = "Dr. Test",
    whatsapp_phone: str | None = "+18095551234",
) -> DoctorModel:
    now = _now()
    doctor = DoctorModel(
        id=doctor_id or str(uuid.uuid4()),
        name=name,
        normalized_name=" ".join(name.strip().lower().split()),
        sex="male",
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        active=True,
        service_active=True,
        service_inactive_reason_id=None,
        service_inactive_detail=None,
        participa_misiones=True,
        whatsapp_phone=whatsapp_phone,
        monthly_service_target=3,
        monthly_service_max=6,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        created_by=_ACTOR,
        created_at=now,
        updated_at=now,
        deactivated_at=None,
        deactivated_by=None,
    )
    db_session.add(doctor)
    db_session.flush()
    return doctor


def _make_assignment(*, doctor_id: str, assignment_id: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=assignment_id or str(uuid.uuid4()),
        doctor_id=doctor_id,
        service_date=datetime.date(2026, 5, 1),
        service_area_id="emergencia",
    )


def _make_mission(*, mission_id: str | None = None) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=mission_id or str(uuid.uuid4()),
        mission_date=datetime.date(2026, 5, 10),
        location="Base Sur",
        description=None,
    )


def _make_participant(*, doctor_id: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(id=str(uuid.uuid4()), doctor_id=doctor_id)


# ---------------------------------------------------------------------------
# Tests — on_calendar_approved
# ---------------------------------------------------------------------------


def test_on_calendar_approved_queues_notifications(db_session) -> None:
    """on_calendar_approved() queues one notification per assignment."""
    doc1 = _create_doctor(db_session, name="Dr. Alpha", whatsapp_phone="+18095551111")
    doc2 = _create_doctor(db_session, name="Dr. Beta", whatsapp_phone="+18095552222")

    a1 = _make_assignment(doctor_id=doc1.id)
    a2 = _make_assignment(doctor_id=doc2.id)

    triggers = _make_triggers(db_session)
    count = triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[a1, a2])

    assert count == 2

    repo = NotificationRepository(db_session)
    all_events = repo.list_all()
    assert len(all_events) == 2


def test_on_calendar_approved_idempotent(db_session) -> None:
    """Calling on_calendar_approved() twice with the same assignments does not create duplicates."""
    doc1 = _create_doctor(db_session, name="Dr. Gamma", whatsapp_phone="+18095553333")
    doc2 = _create_doctor(db_session, name="Dr. Delta", whatsapp_phone="+18095554444")

    a1 = _make_assignment(doctor_id=doc1.id, assignment_id="assign-idempotent-1")
    a2 = _make_assignment(doctor_id=doc2.id, assignment_id="assign-idempotent-2")

    triggers = _make_triggers(db_session)
    triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[a1, a2])
    triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[a1, a2])

    repo = NotificationRepository(db_session)
    all_events = repo.list_all()
    # Each assignment has a fixed idempotency key "assign:<id>", so only 2 rows total
    assert len(all_events) == 2


def test_on_calendar_approved_creates_confirmation_requests(db_session) -> None:
    doc1 = _create_doctor(db_session, name="Dr. Confirm Service", whatsapp_phone="+18095553333")
    assignment = _make_assignment(doctor_id=doc1.id, assignment_id="assign-confirm-service")

    triggers = _make_confirming_triggers(db_session)
    triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[assignment])
    triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[assignment])

    confirmations = ConfirmationRequestRepository(db_session).list_all()
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_type == "service"
    assert confirmations[0].status == "pending"
    assert confirmations[0].assignment_id == assignment.id
    assert confirmations[0].due_at is not None
    notification = NotificationRepository(db_session).list_all()[0]
    assert confirmations[0].response_token in notification.payload["message"]
    assert "/confirmacion-medica?token=" in notification.payload["message"]
    assert "/confirmar " not in notification.payload["message"]
    assert "rechazar" not in notification.payload["message"].lower()


# ---------------------------------------------------------------------------
# Tests — on_mission_confirmed
# ---------------------------------------------------------------------------


def test_on_mission_confirmed_queues_participant_and_summary(db_session) -> None:
    """on_mission_confirmed() queues 2 participant notifications + 1 summary = 3 total."""
    doc1 = _create_doctor(db_session, name="Dr. Echo", whatsapp_phone="+18095555555")
    doc2 = _create_doctor(db_session, name="Dr. Foxtrot", whatsapp_phone="+18095556666")

    mission = _make_mission()
    p1 = _make_participant(doctor_id=doc1.id)
    p2 = _make_participant(doctor_id=doc2.id)

    triggers = _make_triggers(db_session)
    count = triggers.on_mission_confirmed(
        actor_id=_ACTOR,
        mission=mission,
        participants=[p1, p2],
        encargado_phone="+18095559999",
    )

    assert count == 3

    repo = NotificationRepository(db_session)
    all_events = repo.list_all()
    assert len(all_events) == 3

    notification_types = {e.notification_type for e in all_events}
    assert "mission_participant" in notification_types
    assert "mission_summary" in notification_types


def test_on_mission_confirmed_no_summary_without_encargado_phone(db_session) -> None:
    """When encargado_phone is None, only participant notifications are queued."""
    doc1 = _create_doctor(db_session, name="Dr. Golf", whatsapp_phone="+18095557777")
    doc2 = _create_doctor(db_session, name="Dr. Hotel", whatsapp_phone="+18095558888")

    mission = _make_mission()
    p1 = _make_participant(doctor_id=doc1.id)
    p2 = _make_participant(doctor_id=doc2.id)

    triggers = _make_triggers(db_session)
    count = triggers.on_mission_confirmed(
        actor_id=_ACTOR,
        mission=mission,
        participants=[p1, p2],
        encargado_phone=None,
    )

    assert count == 2

    repo = NotificationRepository(db_session)
    all_events = repo.list_all()
    assert len(all_events) == 2

    notification_types = {e.notification_type for e in all_events}
    assert "mission_summary" not in notification_types
    assert "mission_participant" in notification_types


def test_on_mission_confirmed_creates_confirmation_requests(db_session) -> None:
    doc1 = _create_doctor(db_session, name="Dr. Confirm Mission", whatsapp_phone="+18095557777")
    mission = _make_mission(mission_id="mission-confirm")
    participant = _make_participant(doctor_id=doc1.id)

    triggers = _make_confirming_triggers(db_session)
    triggers.on_mission_confirmed(
        actor_id=_ACTOR,
        mission=mission,
        participants=[participant],
        encargado_phone=None,
    )
    triggers.on_mission_confirmed(
        actor_id=_ACTOR,
        mission=mission,
        participants=[participant],
        encargado_phone=None,
    )

    confirmations = ConfirmationRequestRepository(db_session).list_all()
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_type == "mission"
    assert confirmations[0].status == "pending"
    assert confirmations[0].mission_id == mission.id
    assert confirmations[0].due_at is not None
    notification = NotificationRepository(db_session).list_all()[0]
    assert confirmations[0].response_token in notification.payload["message"]
    assert "/confirmacion-medica?token=" in notification.payload["message"]
    assert "/confirmar " not in notification.payload["message"]
    assert "rechazar" not in notification.payload["message"].lower()


def test_calendar_assignment_added_after_approval_creates_change_confirmation(db_session) -> None:
    doc1 = _create_doctor(db_session, name="Dr. Calendar Change", whatsapp_phone="+18095550001")
    assignment = _make_assignment(doctor_id=doc1.id, assignment_id="assign-calendar-change")

    triggers = _make_confirming_triggers(db_session)
    triggers.on_calendar_assignment_added_after_approval(
        actor_id=_ACTOR,
        assignment=assignment,
        service_area_name="Emergencia",
    )
    triggers.on_calendar_assignment_added_after_approval(
        actor_id=_ACTOR,
        assignment=assignment,
        service_area_name="Emergencia",
    )

    events = NotificationRepository(db_session).list_all()
    confirmations = ConfirmationRequestRepository(db_session).list_all()

    assert len(events) == 1
    assert events[0].notification_type == "service_assignment_added"
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_type == "service"
    assert confirmations[0].assignment_id == assignment.id
    assert confirmations[0].response_token in events[0].payload["message"]


def test_mission_participants_changed_notifies_removed_and_confirms_added(db_session) -> None:
    removed = _create_doctor(db_session, name="Dr. Removed", whatsapp_phone="+18095550002")
    added = _create_doctor(db_session, name="Dr. Added", whatsapp_phone="+18095550003")
    mission = _make_mission(mission_id="mission-change")

    removed_participant = _make_participant(doctor_id=removed.id)
    added_participant = _make_participant(doctor_id=added.id)

    triggers = _make_confirming_triggers(db_session)
    count = triggers.on_mission_participants_changed(
        actor_id=_ACTOR,
        mission=mission,
        removed_participants=[removed_participant],
        added_participants=[added_participant],
    )

    events = NotificationRepository(db_session).list_all()
    confirmations = ConfirmationRequestRepository(db_session).list_all()

    assert count == 2
    assert {event.notification_type for event in events} == {
        "mission_participant_removed",
        "mission_participant_added",
    }
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_type == "mission"
    assert confirmations[0].doctor_id == added.id
