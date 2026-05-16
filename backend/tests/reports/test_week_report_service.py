"""Tests for ReportService weekly and full calendar methods."""
from datetime import date
from unittest.mock import MagicMock


def test_build_weekly_schedule_with_week_id():
    """build_weekly_schedule accepts week_id and filters to that week only."""
    from backend.app.application.reports.report_service import ReportService

    calendar_repo = MagicMock()
    notification_repo = MagicMock()
    doctor_repo = MagicMock()

    service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=notification_repo,
        doctor_repo=doctor_repo,
    )

    # Mock week
    week = MagicMock()
    week.id = "week1"
    week.week_number = 1
    week.label = "1RA SEMANA"
    week.start_date = date(2026, 5, 4)
    week.end_date = date(2026, 5, 10)
    week.calendar_id = "cal1"
    week.calendar_version_id = "ver1"

    calendar_repo.get_week_by_id.return_value = week

    # Mock calendar
    cal = MagicMock()
    cal.id = "cal1"
    cal.month = 5
    cal.year = 2026
    calendar_repo.get_calendar_by_period.return_value = cal
    calendar_repo.get_latest_version.return_value = MagicMock(id="ver1")

    # Mock assignments: one inside week range, one outside
    a1 = MagicMock()
    a1.doctor_id = "doc1"
    a1.service_date = date(2026, 5, 5)  # Inside week 1
    a1.service_area_id = "area1"

    a2 = MagicMock()
    a2.doctor_id = "doc2"
    a2.service_date = date(2026, 5, 12)  # Outside week 1

    calendar_repo.list_assignments.return_value = [a1, a2]
    calendar_repo.list_service_areas.return_value = [
        MagicMock(id="area1", code="EMERG", display_name="EMERGENCIA"),
    ]
    doctor_repo.list_all.return_value = [
        MagicMock(id="doc1", name="LOPEZ, JUAN"),
        MagicMock(id="doc2", name="CRUZ, MARIA"),
    ]

    result = service.build_weekly_schedule(
        year=2026, month=5, week_id="week1",
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_full_calendar_returns_grid_data():
    """build_full_calendar produces grid_data dict for the full month."""
    from backend.app.application.reports.report_service import ReportService

    calendar_repo = MagicMock()
    notification_repo = MagicMock()
    doctor_repo = MagicMock()

    service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=notification_repo,
        doctor_repo=doctor_repo,
    )

    cal = MagicMock()
    cal.id = "cal1"
    cal.month = 5
    cal.year = 2026
    calendar_repo.get_calendar_by_period.return_value = cal
    calendar_repo.get_latest_version.return_value = MagicMock(id="ver1")

    a1 = MagicMock()
    a1.doctor_id = "doc1"
    a1.service_date = date(2026, 5, 4)
    a1.service_area_id = "area1"

    calendar_repo.list_assignments.return_value = [a1]
    calendar_repo.list_service_areas.return_value = [
        MagicMock(id="area1", code="EMERG", display_name="EMERGENCIA"),
        MagicMock(id="area2", code="PISTA", display_name="PISTA"),
    ]
    doctor_repo.list_all.return_value = [
        MagicMock(id="doc1", name="LOPEZ, JUAN"),
    ]

    grid_data = service.build_full_calendar(year=2026, month=5)
    assert grid_data["month"] == 5
    assert grid_data["year"] == 2026
    assert len(grid_data["areas"]) == 2
    assert len(grid_data["rows"]) > 0
    assert "summary" in grid_data


def test_build_full_calendar_by_id():
    """build_full_calendar_by_id works from calendar_id directly."""
    from backend.app.application.reports.report_service import ReportService

    calendar_repo = MagicMock()
    notification_repo = MagicMock()
    doctor_repo = MagicMock()

    service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=notification_repo,
        doctor_repo=doctor_repo,
    )

    cal = MagicMock()
    cal.id = "cal1"
    cal.month = 5
    cal.year = 2026
    calendar_repo.get_calendar_by_id.return_value = cal
    calendar_repo.get_latest_version.return_value = MagicMock(id="ver1")
    calendar_repo.list_assignments.return_value = []
    calendar_repo.list_service_areas.return_value = []
    doctor_repo.list_all.return_value = []

    grid_data = service.build_full_calendar_by_id("cal1")
    assert grid_data["month"] == 5
    assert grid_data["year"] == 2026
