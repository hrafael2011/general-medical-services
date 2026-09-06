import pytest

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.repositories.audit import AuditRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository


def _make_service(db_session) -> CalendarService:
    return CalendarService(CalendarRepository(db_session))


class _FakeMissionRankingService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_ranking(self, **kwargs):
        self.calls.append(kwargs)


class _FakeTriggers:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def on_calendar_approved(self, **kwargs):
        self.calls.append(kwargs)
        return len(kwargs.get("assignments", []))


# ---------------------------------------------------------------------------
# create_calendar
# ---------------------------------------------------------------------------


def test_create_calendar_stores_fields(db_session) -> None:
    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001",
        month=5,
        year=2026,
        notes=None,
    )

    assert calendar.month == 5
    assert calendar.year == 2026
    assert calendar.status == "draft"
    assert calendar.generation_mode == "manual"

    versions = repo.list_versions(calendar.id)
    assert len(versions) == 1
    v1 = versions[0]
    assert v1.version_number == 1
    assert v1.status == "draft"


def test_create_calendar_stores_generation_mode(db_session) -> None:
    service = _make_service(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001",
        month=5,
        year=2026,
        notes=None,
        generation_mode="scheduled_auto",
    )

    assert calendar.generation_mode == "scheduled_auto"


def test_create_calendar_duplicate_raises(db_session) -> None:
    service = _make_service(db_session)

    service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    assert exc_info.value.code == "calendar_already_exists"


# ---------------------------------------------------------------------------
# list_calendars
# ---------------------------------------------------------------------------


def test_list_calendars_returns_all(db_session) -> None:
    service = _make_service(db_session)

    service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)
    service.create_calendar(actor_id="actor-001", month=6, year=2026, notes=None)

    calendars = service.list_calendars()
    assert len(calendars) == 2


# ---------------------------------------------------------------------------
# approve_version
# ---------------------------------------------------------------------------


def test_approve_version(db_session) -> None:
    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001", month=5, year=2026, notes=None
    )

    version = service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=1,
        notes=None,
    )

    assert version.status == "approved"

    updated_calendar = repo.get_calendar_by_id(calendar.id)
    assert updated_calendar.status == "approved"


def test_approve_version_generates_mission_ranking(db_session) -> None:
    ranking_service = _FakeMissionRankingService()
    service = CalendarService(
        CalendarRepository(db_session),
        mission_ranking_service=ranking_service,
    )

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    # create_calendar emits an initial (empty) ranking for the new version
    assert len(ranking_service.calls) == 1
    initial_call = ranking_service.calls[0]
    initial_version_id = initial_call["calendar_version_id"]
    assert initial_call == {
        "actor_id": "actor-001",
        "year": 2026,
        "month": 5,
        "calendar_version_id": initial_version_id,
    }

    version = service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=1,
        notes=None,
    )

    # approve_version emits the definitive ranking for the approved version
    assert ranking_service.calls == [
        initial_call,
        {
            "actor_id": "actor-001",
            "year": 2026,
            "month": 5,
            "calendar_version_id": version.id,
        },
    ]


def test_approve_version_is_only_approval_boundary(db_session) -> None:
    ranking_service = _FakeMissionRankingService()
    triggers = _FakeTriggers()
    audit_repo = AuditRepository(db_session)
    service = CalendarService(
        CalendarRepository(db_session),
        audit=AuditService(audit_repo),
        triggers=triggers,
        mission_ranking_service=ranking_service,
    )

    calendar = service.create_calendar(
        actor_id="actor-001",
        month=5,
        year=2026,
        notes=None,
        generation_mode="assisted_auto",
    )
    version = CalendarRepository(db_session).get_latest_version(calendar.id)
    assignment = CalendarAssignmentModel(
        id="assignment-approval-boundary",
        calendar_version_id=version.id,
        service_date=calendar.created_at.date(),
        service_area_id="area-001",
        doctor_id="doctor-001",
        assignment_source="manual",
        rationale=None,
        override_justification=None,
        created_by="actor-001",
        created_at=calendar.created_at,
    )
    CalendarRepository(db_session).add_assignment(assignment)

    assert calendar.status == "draft"
    assert version.status == "draft"
    # create_calendar emits the initial ranking; adding assignments must not
    # emit another one — approve_version is the only ranking boundary.
    assert ranking_service.calls == [
        {
            "actor_id": "actor-001",
            "year": 2026,
            "month": 5,
            "calendar_version_id": version.id,
        }
    ]
    assert triggers.calls == []
    assert audit_repo.count(action_type="calendar_approved") == 0

    approved = service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=version.version_number,
        notes=None,
    )

    assert approved.status == "approved"
    assert calendar.status == "approved"
    assert ranking_service.calls == [
        {
            "actor_id": "actor-001",
            "year": 2026,
            "month": 5,
            "calendar_version_id": version.id,
        },
        {
            "actor_id": "actor-001",
            "year": 2026,
            "month": 5,
            "calendar_version_id": version.id,
        },
    ]
    assert len(triggers.calls) == 1
    assert triggers.calls[0]["assignments"] == [assignment]
    assert audit_repo.count(action_type="calendar_approved") == 1


def test_approve_already_approved_raises(db_session) -> None:
    service = _make_service(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001", month=5, year=2026, notes=None
    )
    service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=1,
        notes=None,
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.approve_version(
            actor_id="actor-001",
            calendar_id=calendar.id,
            version_number=1,
            notes=None,
        )

    assert exc_info.value.code == "calendar_already_approved"


def test_reapprove_unlocked_calendar_does_not_send_initial_notifications(db_session) -> None:
    triggers = _FakeTriggers()
    service = CalendarService(
        CalendarRepository(db_session),
        triggers=triggers,
    )
    repo = CalendarRepository(db_session)
    calendar = service.create_calendar(
        actor_id="actor-001",
        month=5,
        year=2026,
        notes=None,
    )
    version = repo.get_latest_version(calendar.id)
    assignment = CalendarAssignmentModel(
        id="assignment-unlock-reapprove",
        calendar_version_id=version.id,
        service_date=calendar.created_at.date(),
        service_area_id="area-001",
        doctor_id="doctor-001",
        assignment_source="manual",
        rationale=None,
        override_justification=None,
        created_by="actor-001",
        created_at=calendar.created_at,
    )
    repo.add_assignment(assignment)

    service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=version.version_number,
        notes=None,
    )
    assert len(triggers.calls) == 1

    service.unlock_calendar(actor_id="actor-001", calendar_id=calendar.id)
    service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=version.version_number,
        notes=None,
    )

    assert len(triggers.calls) == 1


# ---------------------------------------------------------------------------
# new_version_after_approval
# ---------------------------------------------------------------------------


def test_new_version_after_approval(db_session) -> None:
    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001", month=5, year=2026, notes=None
    )
    service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=1,
        notes=None,
    )

    v2 = service.new_version_after_approval(
        actor_id="actor-001",
        calendar_id=calendar.id,
        reason="Correction needed",
    )

    assert v2.version_number == 2
    assert v2.status == "draft"

    updated_calendar = repo.get_calendar_by_id(calendar.id)
    assert updated_calendar.status == "draft"


def test_new_version_without_approval_raises(db_session) -> None:
    service = _make_service(db_session)

    calendar = service.create_calendar(
        actor_id="actor-001", month=5, year=2026, notes=None
    )

    with pytest.raises(CalendarServiceError) as exc_info:
        service.new_version_after_approval(
            actor_id="actor-001",
            calendar_id=calendar.id,
            reason=None,
        )

    assert exc_info.value.code == "invalid_status_transition"


# ---------------------------------------------------------------------------
# soft_delete / restore / hard_delete
# ---------------------------------------------------------------------------


def test_delete_calendar_cascades_to_versions(db_session) -> None:
    """Deleting a calendar permanently removes it and all its versions."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import select

    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    v2 = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=2,
        status="draft",
        created_by="actor-001",
        created_at=datetime.now(UTC),
    )
    repo.add_version(v2)

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=calendar.id)

    # Permanent deletion: the calendar row is gone from the DB
    assert repo.get_calendar_by_id_including_deleted(calendar.id) is None

    # All versions were deleted in the cascade (not just hidden)
    versions_raw = list(
        db_session.scalars(
            select(CalendarVersionModel).where(CalendarVersionModel.calendar_id == calendar.id)
        )
    )
    assert versions_raw == []


def test_restore_deleted_calendar_raises(db_session) -> None:
    """Deleted calendars are permanently removed, so restore raises calendar_not_found."""
    from datetime import UTC, datetime
    from uuid import uuid4

    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)
    v2 = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=2,
        status="draft",
        created_by="actor-001",
        created_at=datetime.now(UTC),
    )
    repo.add_version(v2)

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=calendar.id)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.restore_calendar(actor_id="actor-001", calendar_id=calendar.id)

    assert exc_info.value.code == "calendar_not_found"


def test_restore_non_deleted_calendar_raises(db_session) -> None:
    """Restoring a calendar that is not deleted raises CalendarServiceError."""
    service = _make_service(db_session)

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.restore_calendar(actor_id="actor-001", calendar_id=calendar.id)

    assert exc_info.value.code == "calendar_not_deleted"


def test_list_deleted_calendars(db_session) -> None:
    """Deletion is permanent, so list_deleted_calendars stays empty."""
    service = _make_service(db_session)

    c1 = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)
    c2 = service.create_calendar(actor_id="actor-001", month=6, year=2026, notes=None)
    c3 = service.create_calendar(actor_id="actor-001", month=7, year=2026, notes=None)

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=c1.id)
    service.soft_delete_calendar(actor_id="actor-001", calendar_id=c2.id)

    deleted = service.list_deleted_calendars()
    assert deleted == []

    remaining = service.list_calendars()
    remaining_ids = {c.id for c in remaining}
    assert c1.id not in remaining_ids
    assert c2.id not in remaining_ids
    assert c3.id in remaining_ids


def test_get_calendar_including_deleted(db_session) -> None:
    """After permanent deletion no query (including _including_deleted) returns the row."""
    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)

    assert repo.get_calendar_by_id_including_deleted(calendar.id) is not None

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=calendar.id)

    assert repo.get_calendar_by_id(calendar.id) is None
    assert repo.get_calendar_by_id_including_deleted(calendar.id) is None


def test_delete_calendar_does_not_affect_other_calendars(db_session) -> None:
    """Deleting one calendar does not touch other calendars or their versions."""
    from datetime import UTC, datetime
    from uuid import uuid4

    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    c1 = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)
    c2 = service.create_calendar(actor_id="actor-001", month=6, year=2026, notes=None)

    v2 = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=c2.id,
        version_number=2,
        status="draft",
        created_by="actor-001",
        created_at=datetime.now(UTC),
    )
    repo.add_version(v2)

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=c1.id)

    found = repo.get_calendar_by_id(c2.id)
    assert found is not None
    assert found.deleted_at is None

    versions = repo.list_versions(c2.id)
    assert len(versions) == 2
    for v in versions:
        assert v.deleted_at is None


def test_version_queries_after_permanent_delete(db_session) -> None:
    """get_version_by_id, list_versions, get_latest_version return nothing after deletion."""
    from datetime import UTC, datetime
    from uuid import uuid4

    service = _make_service(db_session)
    repo = CalendarRepository(db_session)

    calendar = service.create_calendar(actor_id="actor-001", month=5, year=2026, notes=None)
    v2 = CalendarVersionModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        version_number=2,
        status="draft",
        created_by="actor-001",
        created_at=datetime.now(UTC),
    )
    repo.add_version(v2)

    service.soft_delete_calendar(actor_id="actor-001", calendar_id=calendar.id)

    assert repo.get_version_by_id(v2.id) is None
    assert len(repo.list_versions(calendar.id)) == 0
    assert repo.get_latest_version(calendar.id) is None
