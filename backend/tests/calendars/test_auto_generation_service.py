from datetime import date
from types import SimpleNamespace

from backend.app.application.calendars.auto_generation_service import (
    AutoCalendarGenerationService,
    SYSTEM_AUTO_GENERATION_ACTOR,
)
from backend.app.application.calendars.service import CalendarService
from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository


class _FakeGenerationService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(assigned_count=93, gap_count=0)


def _make_service(db_session) -> tuple[
    AutoCalendarGenerationService,
    CalendarRepository,
    CatalogService,
    _FakeGenerationService,
]:
    calendar_repo = CalendarRepository(db_session)
    catalog_service = CatalogService(CatalogRepository(db_session))
    generation = _FakeGenerationService()
    service = AutoCalendarGenerationService(
        calendar_service=CalendarService(calendar_repo),
        generation_service=generation,
        catalog_service=catalog_service,
    )
    return service, calendar_repo, catalog_service, generation


def test_run_due_skips_when_disabled(db_session) -> None:
    service, _calendar_repo, _catalog_service, generation = _make_service(db_session)

    result = service.run_due(today=date(2026, 5, 27))

    assert result["status"] == "skipped"
    assert result["reason"] == "disabled"
    assert generation.calls == []


def test_run_due_skips_when_not_due(db_session) -> None:
    service, _calendar_repo, catalog_service, generation = _make_service(db_session)
    catalog_service.update_calendar_generation_settings(
        auto_generation_enabled=True,
        generation_day=25,
    )

    result = service.run_due(today=date(2026, 5, 24))

    assert result["status"] == "skipped"
    assert result["reason"] == "not_due"
    assert generation.calls == []


def test_run_due_creates_next_month_draft_and_generates(db_session) -> None:
    service, calendar_repo, catalog_service, generation = _make_service(db_session)
    catalog_service.update_calendar_generation_settings(
        auto_generation_enabled=True,
        generation_day=25,
    )

    result = service.run_due(today=date(2026, 5, 25))

    assert result["status"] == "generated"
    assert result["month"] == 6
    assert result["year"] == 2026
    assert result["assigned_count"] == 93
    assert result["gap_count"] == 0

    calendar = calendar_repo.get_calendar_by_period(2026, 6)
    assert calendar is not None
    assert calendar.status == "draft"
    assert calendar.generation_mode == "scheduled_auto"
    assert calendar.created_by == SYSTEM_AUTO_GENERATION_ACTOR
    assert generation.calls == [
        {
            "actor_id": SYSTEM_AUTO_GENERATION_ACTOR,
            "calendar_id": calendar.id,
            "generation_mode": "scheduled_auto",
        }
    ]


def test_run_due_skips_existing_calendar(db_session) -> None:
    service, calendar_repo, catalog_service, generation = _make_service(db_session)
    catalog_service.update_calendar_generation_settings(
        auto_generation_enabled=True,
        generation_day=25,
    )
    existing = CalendarService(calendar_repo).create_calendar(
        actor_id="actor-001",
        month=6,
        year=2026,
        notes=None,
    )

    result = service.run_due(today=date(2026, 5, 25))

    assert result["status"] == "skipped"
    assert result["reason"] == "calendar_already_exists"
    assert result["calendar_id"] == existing.id
    assert generation.calls == []
