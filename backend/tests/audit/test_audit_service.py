import pytest

from backend.app.application.accounts.errors import InvalidCredentialsError
from backend.app.application.accounts.service import AccountService
from backend.app.application.audit.service import AuditService
from backend.app.application.doctors.service import DoctorService
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.users import UserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_audit_service(db_session) -> AuditService:
    return AuditService(AuditRepository(db_session))


def make_doctor_service(db_session, audit_service=None) -> DoctorService:
    return DoctorService(DoctorRepository(db_session), audit=audit_service)


def create_doctor(db_session, service, *, name="Dr Test", sex="male"):
    return service.create_doctor(
        actor_id="actor-1",
        name=name,
        sex=sex,
        rank_id=None,
        department_id=None,
        phone=None,
        notes=None,
        participa_misiones=True,
        whatsapp_phone=None,
        monthly_service_target=3,
        monthly_service_max=3,
        monthly_service_limit_mode="warn_only",
        availability_mode="monthly",
        allowed_area_ids=[],
    )


def _bootstrap_admin(service: AccountService):
    """Create an admin user and clear the must_change_password flag."""
    result = service.ensure_admin_password(
        email="admin@test.local",
        name="Admin",
        temporary_password="Temporary123!",
    )
    admin = result.user
    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    return admin


# ---------------------------------------------------------------------------
# Doctor audit tests
# ---------------------------------------------------------------------------

def test_audit_event_is_created_when_doctor_is_created(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    create_doctor(db_session, doctor_service)

    events = audit.repo.list()
    assert len(events) == 1
    assert events[0].action_type == "doctor_created"
    assert events[0].entity_type == "doctor"


def test_audit_event_contains_doctor_name_in_after_snapshot(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor = create_doctor(db_session, doctor_service, name="Dr. Snapshot")

    events = audit.repo.list()
    assert len(events) == 1
    assert events[0].after_snapshot is not None
    assert events[0].after_snapshot["name"] == doctor.name


def test_audit_event_for_service_deactivation(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor = create_doctor(db_session, doctor_service)
    doctor_service.deactivate_service(doctor.id, actor_id="actor-1", reason_id="reason-001", detail=None)

    events = audit.repo.list()
    action_types = [e.action_type for e in events]
    assert "doctor_service_deactivated" in action_types


def test_audit_event_for_service_reactivation(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor = create_doctor(db_session, doctor_service)
    doctor_service.deactivate_service(doctor.id, actor_id="actor-1", reason_id="reason-001", detail=None)
    doctor_service.reactivate_service(doctor.id, actor_id="actor-1")

    events = audit.repo.list()
    action_types = [e.action_type for e in events]
    assert "doctor_service_reactivated" in action_types


def test_no_audit_event_without_audit_service(db_session) -> None:
    audit_repo = AuditRepository(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=None)

    create_doctor(db_session, doctor_service)

    events = audit_repo.list()
    assert len(events) == 0


# ---------------------------------------------------------------------------
# Append-only / ordering
# ---------------------------------------------------------------------------

def test_append_only_no_update_method(db_session) -> None:
    """AuditRepository exposes no update or delete — all events are preserved
    and returned in descending order by occurred_at."""
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor = create_doctor(db_session, doctor_service)
    doctor_service.deactivate_service(doctor.id, actor_id="actor-1", reason_id="r1", detail=None)
    doctor_service.reactivate_service(doctor.id, actor_id="actor-1")

    assert not hasattr(audit.repo, "update")
    assert not hasattr(audit.repo, "delete")

    events = audit.repo.list()
    assert len(events) == 3
    # list() orders by occurred_at DESC — first item is the most recent
    assert events[0].action_type == "doctor_service_reactivated"
    assert events[1].action_type == "doctor_service_deactivated"
    assert events[2].action_type == "doctor_created"


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------

def test_filter_by_actor_id(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service_a = make_doctor_service(db_session, audit_service=audit)
    doctor_service_b = DoctorService(
        DoctorRepository(db_session), audit=audit
    )

    # actor-1 creates a doctor
    doctor_service_a.create_doctor(
        actor_id="actor-1", name="Dr A", sex="male",
        rank_id=None, department_id=None, phone=None, notes=None,
        participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )
    # actor-2 creates another doctor
    doctor_service_b.create_doctor(
        actor_id="actor-2", name="Dr B", sex="female",
        rank_id=None, department_id=None, phone=None, notes=None,
        participa_misiones=True, whatsapp_phone=None,
        monthly_service_target=3, monthly_service_max=3,
        monthly_service_limit_mode="warn_only", availability_mode="monthly",
        allowed_area_ids=[],
    )

    events = audit.repo.list(actor_id="actor-1")
    assert len(events) == 1
    assert events[0].actor_id == "actor-1"


def test_filter_by_action_type(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor = create_doctor(db_session, doctor_service)
    doctor_service.deactivate_service(doctor.id, actor_id="actor-1", reason_id="r1", detail=None)

    events = audit.repo.list(action_type="doctor_created")
    assert len(events) == 1
    assert events[0].action_type == "doctor_created"


def test_filter_by_entity_type(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    create_doctor(db_session, doctor_service)

    events = audit.repo.list(entity_type="doctor")
    assert len(events) >= 1
    assert all(e.entity_type == "doctor" for e in events)


def test_filter_by_entity_id(db_session) -> None:
    audit = make_audit_service(db_session)
    doctor_service = make_doctor_service(db_session, audit_service=audit)

    doctor_a = create_doctor(db_session, doctor_service, name="Doctor A")
    doctor_b = create_doctor(db_session, doctor_service, name="Doctor B")

    events = audit.repo.list(entity_id=doctor_a.id)
    assert len(events) == 1
    assert events[0].entity_id == doctor_a.id

    events_b = audit.repo.list(entity_id=doctor_b.id)
    assert len(events_b) == 1
    assert events_b[0].entity_id == doctor_b.id


# ---------------------------------------------------------------------------
# Account audit tests
# ---------------------------------------------------------------------------

def test_login_failed_audit_event(db_session) -> None:
    audit = make_audit_service(db_session)
    account_service = AccountService(UserRepository(db_session), audit=audit)

    account_service.ensure_admin_password(
        email="admin@test.local",
        name="Admin",
        temporary_password="Temporary123!",
    )

    with pytest.raises(InvalidCredentialsError):
        account_service.authenticate("admin@test.local", "wrong-password")

    events = audit.repo.list(action_type="login_failed")
    assert len(events) == 1
    assert events[0].action_type == "login_failed"
    assert events[0].entity_type == "user"


def test_password_changed_audit_event(db_session) -> None:
    audit = make_audit_service(db_session)
    account_service = AccountService(UserRepository(db_session), audit=audit)

    admin = _bootstrap_admin(account_service)

    events = audit.repo.list(action_type="password_changed")
    assert len(events) == 1
    assert events[0].action_type == "password_changed"
    assert events[0].entity_type == "user"
    assert events[0].entity_id == admin.id
    assert events[0].after_snapshot == {"must_change_password": False}
