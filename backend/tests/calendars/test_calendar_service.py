import pytest

from backend.app.application.audit.service import AuditService
from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel
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

    calendar = service.create_calendar(
        actor_id="actor-001", month=5, year=2026, notes=None
    )

    version = service.approve_version(
        actor_id="actor-001",
        calendar_id=calendar.id,
        version_number=1,
        notes=None,
    )

    assert ranking_service.calls == [
        {
            "actor_id": "actor-001",
            "year": 2026,
            "month": 5,
            "calendar_version_id": version.id,
        }
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
    assert ranking_service.calls == []
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
        }
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
