"""Aprobar exige cobertura: cada día del período con médico en cada área requerida."""
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

import pytest

from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.tests.calendars.test_week_service import FakeWeekRepo


@dataclass
class FakeArea:
    code: str
    display_name: str
    active: bool = True
    required_for_daily_coverage: bool = True
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = self.code


AREAS = [
    FakeArea("emergencia", "Emergencia"),
    FakeArea("pista", "Pista"),
    FakeArea("disponible", "Disponible"),
]


class CoverageRepo(FakeWeekRepo):
    def __init__(self, areas=None):
        super().__init__()
        self.areas = AREAS if areas is None else areas

    def list_service_areas(self):
        return self.areas


def _add_assignment(repo, version_id, day, area_code, tag):
    repo.add_assignment(
        CalendarAssignmentModel(
            id=str(uuid4()),
            calendar_version_id=version_id,
            service_date=day,
            service_area_id=area_code,
            doctor_id=f"doc-{tag}",
        )
    )


def _cover_range(repo, version_id, start, end, areas=AREAS):
    day = start
    while day <= end:
        for area in areas:
            _add_assignment(repo, version_id, day, area.code, f"{day}-{area.code}")
        day += timedelta(days=1)


def _calendar_with_week(start, end, year, month):
    repo = CoverageRepo()
    cal = CalendarModel(
        id=str(uuid4()), year=year, month=month, status="draft", generation_mode="manual"
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id, version_number=1, status="draft"
    )
    repo.add_version(version)
    week = CalendarWeekModel(
        id=str(uuid4()),
        calendar_id=cal.id,
        calendar_version_id=version.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=start,
        end_date=end,
        status="draft",
    )
    repo.add_week(week)
    return repo, cal, version, week


def test_approve_week_rejects_a_day_without_doctors():
    repo, _cal, version, week = _calendar_with_week(
        date(2026, 5, 4), date(2026, 5, 10), 2026, 5
    )
    _cover_range(repo, version.id, date(2026, 5, 4), date(2026, 5, 10))
    # Wednesday 06/05 loses every doctor
    repo.assignments = {
        aid: a
        for aid, a in repo.assignments.items()
        if a.service_date != date(2026, 5, 6)
    }

    service = CalendarService(repo=repo, audit=None, triggers=None)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.approve_week(actor_id="user1", week_id=week.id)

    error = exc_info.value
    assert error.code == "week_incomplete"
    assert error.details == [
        {"date": "2026-05-06", "areas": ["Emergencia", "Pista", "Disponible"]}
    ]
    assert "miércoles 06/05" in error.message
    assert repo.weeks[week.id].status == "draft"


def test_approve_week_rejects_a_missing_area_on_every_day():
    repo, _cal, version, week = _calendar_with_week(
        date(2026, 5, 4), date(2026, 5, 10), 2026, 5
    )
    _cover_range(
        repo, version.id, date(2026, 5, 4), date(2026, 5, 10), areas=AREAS[:2]
    )

    service = CalendarService(repo=repo, audit=None, triggers=None)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.approve_week(actor_id="user1", week_id=week.id)

    error = exc_info.value
    assert error.code == "week_incomplete"
    assert len(error.details) == 7
    assert all(detail["areas"] == ["Disponible"] for detail in error.details)


def test_approve_week_passes_when_every_day_and_area_is_covered():
    repo, cal, version, week = _calendar_with_week(
        date(2026, 5, 4), date(2026, 5, 10), 2026, 5
    )
    _cover_range(repo, version.id, date(2026, 5, 4), date(2026, 5, 10))

    service = CalendarService(repo=repo, audit=None, triggers=None)

    result = service.approve_week(actor_id="user1", week_id=week.id)

    assert result.status == "approved"


def test_approve_week_does_not_claim_days_of_the_next_month():
    # June 2026: the last week runs 29/06 → 05/07.
    repo, _cal, version, week = _calendar_with_week(
        date(2026, 6, 29), date(2026, 7, 5), 2026, 6
    )
    _cover_range(repo, version.id, date(2026, 6, 29), date(2026, 6, 30))

    service = CalendarService(repo=repo, audit=None, triggers=None)

    result = service.approve_week(actor_id="user1", week_id=week.id)

    assert result.status == "approved"


def test_approve_week_ignores_areas_that_are_not_required_daily():
    # Una cuarta área activa pero sin cobertura diaria no debe bloquear.
    extra = FakeArea("docencia", "Docencia", required_for_daily_coverage=False)
    repo = CoverageRepo(areas=[*AREAS, extra])
    cal = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="draft", generation_mode="manual"
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id, version_number=1, status="draft"
    )
    repo.add_version(version)
    week = CalendarWeekModel(
        id=str(uuid4()),
        calendar_id=cal.id,
        calendar_version_id=version.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="draft",
    )
    repo.add_week(week)
    _cover_range(repo, version.id, date(2026, 5, 4), date(2026, 5, 10))

    service = CalendarService(repo=repo, audit=None, triggers=None)

    result = service.approve_week(actor_id="user1", week_id=week.id)

    assert result.status == "approved"


def test_approve_version_rejects_a_month_with_an_empty_day():
    repo = CoverageRepo()
    cal = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="draft", generation_mode="manual"
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id, version_number=1, status="draft"
    )
    repo.add_version(version)
    _cover_range(repo, version.id, date(2026, 5, 1), date(2026, 5, 30))

    service = CalendarService(repo=repo, audit=None, triggers=None)

    with pytest.raises(CalendarServiceError) as exc_info:
        service.approve_version(
            actor_id="user1", calendar_id=cal.id, version_number=1, notes=None
        )

    error = exc_info.value
    assert error.code == "calendar_incomplete"
    assert error.details == [
        {"date": "2026-05-31", "areas": ["Emergencia", "Pista", "Disponible"]}
    ]
    assert repo.versions[version.id].status == "draft"


def test_approve_version_passes_when_the_whole_month_is_covered():
    repo = CoverageRepo()
    cal = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="draft", generation_mode="manual"
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id, version_number=1, status="draft"
    )
    repo.add_version(version)
    _cover_range(repo, version.id, date(2026, 5, 1), date(2026, 5, 31))

    service = CalendarService(repo=repo, audit=None, triggers=None)

    result = service.approve_version(
        actor_id="user1", calendar_id=cal.id, version_number=1, notes=None
    )

    assert result.status == "approved"
