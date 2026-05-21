"""Tests for CalendarWeek repository CRUD."""
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from backend.app.infrastructure.db.models.calendars import (
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)
from backend.app.infrastructure.repositories.calendars import CalendarRepository

_NOW = datetime.now(timezone.utc)


@pytest.fixture
def calendar_with_weeks(db_session):
    repo = CalendarRepository(db_session)
    cal = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="draft",
        generation_mode="manual", created_at=_NOW, updated_at=_NOW,
    )
    repo.add_calendar(cal)
    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=cal.id,
        version_number=1, status="draft", created_at=_NOW,
    )
    repo.add_version(version)
    weeks = []
    for i, (label, sd, ed) in enumerate([
        ("1RA SEMANA", date(2026, 5, 4), date(2026, 5, 10)),
        ("2DA SEMANA", date(2026, 5, 11), date(2026, 5, 17)),
    ], start=1):
        w = CalendarWeekModel(
            id=str(uuid4()), calendar_id=cal.id,
            calendar_version_id=version.id,
            week_number=i, label=label,
            start_date=sd, end_date=ed, status="draft",
            created_at=_NOW, updated_at=_NOW,
        )
        repo.add_week(w)
        weeks.append(w)
    db_session.flush()
    return cal, version, weeks


@pytest.mark.db
def test_list_weeks_by_calendar(calendar_with_weeks, db_session):
    repo = CalendarRepository(db_session)
    cal, _, weeks = calendar_with_weeks
    result = repo.list_weeks(cal.id)
    assert len(result) == 2


@pytest.mark.db
def test_get_week_by_id(calendar_with_weeks, db_session):
    repo = CalendarRepository(db_session)
    _, _, weeks = calendar_with_weeks
    w = repo.get_week_by_id(weeks[0].id)
    assert w is not None
    assert w.label == "1RA SEMANA"


@pytest.mark.db
def test_update_week_status(calendar_with_weeks, db_session):
    repo = CalendarRepository(db_session)
    _, _, weeks = calendar_with_weeks
    repo.update_week_status(weeks[0].id, "approved", approved_by="user1")
    db_session.flush()
    w = repo.get_week_by_id(weeks[0].id)
    assert w.status == "approved"
    assert w.approved_by == "user1"
    assert w.approved_at is not None


@pytest.mark.db
def test_list_weeks_by_version(calendar_with_weeks, db_session):
    repo = CalendarRepository(db_session)
    _, version, weeks = calendar_with_weeks
    result = repo.list_weeks_by_version(version.id)
    assert len(result) == 2
