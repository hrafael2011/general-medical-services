import pytest

from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.repositories.calendars import CalendarRepository


def _make_service(db_session) -> CalendarService:
    return CalendarService(CalendarRepository(db_session))


class _FakeMissionRankingService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_ranking(self, **kwargs):
        self.calls.append(kwargs)


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

    versions = repo.list_versions(calendar.id)
    assert len(versions) == 1
    v1 = versions[0]
    assert v1.version_number == 1
    assert v1.status == "draft"


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
