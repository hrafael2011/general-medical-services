"""Tests for CalendarWeekModel persistence."""
import pytest
from datetime import date, datetime, timezone
from uuid import uuid4
from backend.app.infrastructure.db.models.calendars import (
    CalendarWeekModel, CalendarModel, CalendarVersionModel
)

_NOW = datetime.now(timezone.utc)


@pytest.mark.db
def test_calendar_week_model_insert(db_session):
    """CalendarWeekModel can be inserted with required fields."""
    calendar = CalendarModel(
        id=str(uuid4()), year=2026, month=5, status="draft",
        generation_mode="manual",
        created_at=_NOW, updated_at=_NOW,
    )
    db_session.add(calendar)
    db_session.flush()

    version = CalendarVersionModel(
        id=str(uuid4()), calendar_id=calendar.id,
        version_number=1, status="draft", created_at=_NOW,
    )
    db_session.add(version)
    db_session.flush()

    week = CalendarWeekModel(
        id=str(uuid4()),
        calendar_id=calendar.id,
        calendar_version_id=version.id,
        week_number=1,
        label="1RA SEMANA",
        start_date=date(2026, 5, 4),
        end_date=date(2026, 5, 10),
        status="draft",
        created_at=_NOW, updated_at=_NOW,
    )
    db_session.add(week)
    db_session.flush()

    assert week.id is not None
    assert week.status == "draft"
    assert week.week_number == 1


@pytest.mark.db
def test_calendar_assignment_has_week_id(db_session):
    """CalendarAssignmentModel accepts calendar_week_id FK."""
    from backend.app.infrastructure.db.models.calendars import CalendarAssignmentModel
    assert hasattr(CalendarAssignmentModel, "calendar_week_id")
