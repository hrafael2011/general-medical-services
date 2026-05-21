"""Tests for CalendarService week approval and unlock methods."""
import hashlib
import pytest
from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.application.calendars.errors import CalendarServiceError
from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import (
    CalendarModel, CalendarVersionModel, CalendarWeekModel,
    CalendarAssignmentModel,
)


class FakeWeekRepo:
    """Minimal fake that stores entities in dicts — no real DB needed."""
    def __init__(self):
        self.weeks = {}
        self.calendars = {}
        self.versions = {}
        self.assignments = {}
        self.session = MagicMock()

    # Week methods (from Task 3)
    def add_week(self, week):
        self.weeks[week.id] = week; return week

    def get_week_by_id(self, week_id):
        return self.weeks.get(week_id)

    def list_weeks(self, calendar_id):
        return [w for w in self.weeks.values() if w.calendar_id == calendar_id]

    def list_weeks_by_version(self, version_id):
        return [w for w in self.weeks.values() if w.calendar_version_id == version_id]

    def update_week_status(self, week_id, status, approved_by=None, previous_assignments_hash=None):
        w = self.weeks.get(week_id)
        if w:
            w.status = status
            if approved_by:
                w.approved_by = approved_by
                w.approved_at = True  # truthy sentinel
            if previous_assignments_hash is not None:
                w.previous_assignments_hash = previous_assignments_hash

    # Calendar methods
    def get_calendar_by_id(self, calendar_id):
        return self.calendars.get(calendar_id)

    def add_calendar(self, cal):
        self.calendars[cal.id] = cal; return cal

    # Version methods
    def get_version_by_id(self, version_id):
        return self.versions.get(version_id)

    def list_versions(self, calendar_id):
        return [v for v in self.versions.values() if v.calendar_id == calendar_id]

    def add_version(self, v):
        self.versions[v.id] = v; return v

    # Assignment methods
    def list_assignments(self, version_id):
        return [a for a in self.assignments.values() if a.calendar_version_id == version_id]

    def add_assignment(self, a):
        self.assignments[a.id] = a; return a


def test_approve_week_updates_status():
    """approve_week sets week to approved and calendar to partial."""
    repo = FakeWeekRepo()
    cal = CalendarModel(id=str(uuid4()), year=2026, month=5, status="draft",
                        generation_mode="manual")
    repo.add_calendar(cal)
    version = CalendarVersionModel(id=str(uuid4()), calendar_id=cal.id,
                                   version_number=1, status="draft")
    repo.add_version(version)
    week = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                             calendar_version_id=version.id,
                             week_number=1, label="1RA SEMANA",
                             start_date=date(2026, 5, 4),
                             end_date=date(2026, 5, 10), status="draft")
    repo.add_week(week)
    # Second week stays in draft so calendar becomes "partial", not "approved"
    week2 = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                              calendar_version_id=version.id,
                              week_number=2, label="2DA SEMANA",
                              start_date=date(2026, 5, 11),
                              end_date=date(2026, 5, 17), status="draft")
    repo.add_week(week2)

    triggers = MagicMock()
    service = CalendarService(repo=repo, triggers=triggers, audit=None)

    result = service.approve_week(actor_id="user1", week_id=week.id, notes=None)

    assert result.status == "approved"
    assert cal.status == "partial"
    # triggers.on_week_approved should be called
    triggers.on_week_approved.assert_called_once()


def test_approve_week_already_approved_raises():
    """Approving an already-approved week raises CalendarServiceError."""
    repo = FakeWeekRepo()
    cal = CalendarModel(id=str(uuid4()), year=2026, month=5, status="draft",
                        generation_mode="manual")
    repo.add_calendar(cal)
    version = CalendarVersionModel(id=str(uuid4()), calendar_id=cal.id,
                                   version_number=1, status="draft")
    repo.add_version(version)
    week = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                             calendar_version_id=version.id,
                             week_number=1, label="1RA SEMANA",
                             start_date=date(2026, 5, 4),
                             end_date=date(2026, 5, 10), status="approved")
    repo.add_week(week)

    service = CalendarService(repo=repo, triggers=MagicMock(), audit=None)
    with pytest.raises(CalendarServiceError, match="already approved"):
        service.approve_week(actor_id="user1", week_id=week.id, notes=None)


def test_approve_all_weeks_sets_calendar_approved():
    """When the last week is approved, calendar status becomes 'approved'."""
    repo = FakeWeekRepo()
    cal = CalendarModel(id=str(uuid4()), year=2026, month=5, status="partial",
                        generation_mode="manual")
    repo.add_calendar(cal)
    version = CalendarVersionModel(id=str(uuid4()), calendar_id=cal.id,
                                   version_number=1, status="draft")
    repo.add_version(version)
    w1 = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                           calendar_version_id=version.id,
                           week_number=1, label="1RA SEMANA",
                           start_date=date(2026, 5, 4),
                           end_date=date(2026, 5, 10), status="approved")
    w2 = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                           calendar_version_id=version.id,
                           week_number=2, label="2DA SEMANA",
                           start_date=date(2026, 5, 11),
                           end_date=date(2026, 5, 17), status="draft")
    repo.add_week(w1); repo.add_week(w2)

    triggers = MagicMock()
    service = CalendarService(repo=repo, triggers=triggers, audit=None)
    result = service.approve_week(actor_id="user1", week_id=w2.id, notes=None)

    assert result.status == "approved"
    assert cal.status == "approved"


def test_unlock_week_stores_hash():
    """unlock_week saves MD5 hash of current assignments and reverts to draft."""
    repo = FakeWeekRepo()
    cal = CalendarModel(id=str(uuid4()), year=2026, month=5, status="partial",
                        generation_mode="manual")
    repo.add_calendar(cal)
    version = CalendarVersionModel(id=str(uuid4()), calendar_id=cal.id,
                                   version_number=1, status="draft")
    repo.add_version(version)
    week = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                             calendar_version_id=version.id,
                             week_number=1, label="1RA SEMANA",
                             start_date=date(2026, 5, 4),
                             end_date=date(2026, 5, 10), status="approved")
    repo.add_week(week)
    a1 = CalendarAssignmentModel(id=str(uuid4()), calendar_version_id=version.id,
                                 calendar_week_id=week.id,
                                 service_date=date(2026, 5, 5),
                                 service_area_id="area1", doctor_id="doc1")
    repo.add_assignment(a1)

    service = CalendarService(repo=repo, triggers=MagicMock(), audit=None)
    result = service.unlock_week(actor_id="user1", week_id=week.id, notes="revision")

    assert result.status == "draft"
    assert result.previous_assignments_hash is not None
    expected_hash = hashlib.md5(b"doc1|2026-05-05|area1").hexdigest()
    assert result.previous_assignments_hash == expected_hash
    assert cal.status == "partial"
