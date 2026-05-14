"""Tests for ReportService — generates Excel, JSON and PDF reports from repos."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.app.application.reports.report_service import ReportService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_calendar_repo():
    return MagicMock()


@pytest.fixture
def mock_notification_repo():
    return MagicMock()


@pytest.fixture
def mock_doctor_repo():
    return MagicMock()


@pytest.fixture
def mock_mission_repo():
    return MagicMock()


@pytest.fixture
def mock_catalog_repo():
    return MagicMock()


@pytest.fixture
def service(mock_calendar_repo, mock_notification_repo, mock_doctor_repo, mock_mission_repo, mock_catalog_repo):
    return ReportService(
        calendar_repo=mock_calendar_repo,
        notification_repo=mock_notification_repo,
        doctor_repo=mock_doctor_repo,
        mission_repo=mock_mission_repo,
        catalog_repo=mock_catalog_repo,
    )


# ---------------------------------------------------------------------------
# _load_signatures
# ---------------------------------------------------------------------------


def test_load_signatures_defaults_when_no_catalog(service):
    """Without catalog_repo, returns DEFAULT_SIGNATURES."""
    service.catalog_repo = None
    sig = service._load_signatures()
    assert sig.left_name == "Dra. MIGUELINA A. ACOSTA RAMOS"
    assert sig.right_name == "ING. CARLOS J. ENCARNACION GONZALEZ"


def test_load_signatures_from_settings(service, mock_catalog_repo):
    """With catalog_repo, loads from system_settings."""
    from backend.app.application.reports.pdf_templates import DEFAULT_SIGNATURES

    mock_catalog_repo.get_setting.return_value = None  # all fall back to defaults
    sig = service._load_signatures()
    assert sig.left_name == DEFAULT_SIGNATURES.left_name


def test_load_signatures_custom_value(service, mock_catalog_repo):
    """Custom setting overrides default."""
    mock_setting = MagicMock()
    mock_setting.value = "Dr. Custom"
    mock_catalog_repo.get_setting.return_value = mock_setting

    sig = service._load_signatures()
    assert sig.left_name == "Dr. Custom"


# ---------------------------------------------------------------------------
# generate_calendar_excel
# ---------------------------------------------------------------------------


def test_calendar_excel_returns_xlsx(service, mock_calendar_repo):
    """generate_calendar_excel returns xlsx bytes."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_cal.month = 4
    mock_cal.year = 2026
    mock_calendar_repo.get_calendar_by_id.return_value = mock_cal

    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_calendar_repo.list_assignments.return_value = []

    result = service.generate_calendar_excel("cal-1")
    assert isinstance(result, bytes)
    assert len(result) > 0
    # xlsx magic bytes
    assert result[:2] == b"\x50\x4b"


def test_calendar_excel_with_assignments(service, mock_calendar_repo):
    """Excel includes assignment data rows."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_cal.month = 4
    mock_cal.year = 2026
    mock_calendar_repo.get_calendar_by_id.return_value = mock_cal

    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.service_date = date(2026, 4, 1)
    mock_assignment.service_area_id = "area-1"
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.assignment_source = "manual"
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    result = service.generate_calendar_excel("cal-1")
    assert isinstance(result, bytes)
    assert result[:2] == b"\x50\x4b"


def test_calendar_excel_not_found(service, mock_calendar_repo):
    """Raises ValueError when calendar does not exist."""
    mock_calendar_repo.get_calendar_by_id.return_value = None
    with pytest.raises(ValueError, match="Calendario no encontrado"):
        service.generate_calendar_excel("invalid-id")


def test_calendar_excel_version_not_found(service, mock_calendar_repo):
    """Raises ValueError when no version exists."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_id.return_value = mock_cal
    mock_calendar_repo.get_latest_version.return_value = None

    with pytest.raises(ValueError, match="Calendario no encontrado"):
        service.generate_calendar_excel("cal-1")


# ---------------------------------------------------------------------------
# generate_doctor_history_excel
# ---------------------------------------------------------------------------


def test_doctor_history_excel_returns_xlsx(service, mock_calendar_repo, mock_doctor_repo):
    """generate_doctor_history_excel returns xlsx bytes."""
    mock_doctor_repo.list_all.return_value = []
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_doctor_history_excel(2026, 4)
    assert isinstance(result, bytes)
    assert result[:2] == b"\x50\x4b"


def test_doctor_history_excel_with_data(service, mock_calendar_repo, mock_doctor_repo):
    """Excel includes all doctors with their assignment counts."""
    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Test"
    mock_doctor_repo.list_all.return_value = [mock_doc]

    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal
    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.service_area_id = "area-1"
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    result = service.generate_doctor_history_excel(2026, 4)
    assert isinstance(result, bytes)
    assert result[:2] == b"\x50\x4b"


def test_doctor_history_excel_no_calendar(service, mock_calendar_repo, mock_doctor_repo):
    """When no calendar exists, returns xlsx with zero counts."""
    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Zero"
    mock_doctor_repo.list_all.return_value = [mock_doc]
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_doctor_history_excel(2026, 4)
    assert isinstance(result, bytes)
    assert result[:2] == b"\x50\x4b"


# ---------------------------------------------------------------------------
# generate_notifications_summary
# ---------------------------------------------------------------------------


def test_notifications_summary_empty(service, mock_notification_repo):
    """Returns zero counts when no notifications exist."""
    mock_notification_repo.list_by_period.return_value = []

    result = service.generate_notifications_summary(2026, 4)
    assert result["period"] == {"year": 2026, "month": 4}
    assert result["total"] == 0
    assert result["by_status"] == {"pending": 0, "sent": 0, "failed": 0, "skipped": 0}
    assert result["by_type"] == {}
    assert isinstance(result["generated_at"], str)


def test_notifications_summary_counts(service, mock_notification_repo):
    """Counts notifications by status and type."""
    n1 = MagicMock()
    n1.status = "sent"
    n1.notification_type = "email"
    n2 = MagicMock()
    n2.status = "sent"
    n2.notification_type = "email"
    n3 = MagicMock()
    n3.status = "failed"
    n3.notification_type = "sms"

    mock_notification_repo.list_by_period.return_value = [n1, n2, n3]

    result = service.generate_notifications_summary(2026, 4)
    assert result["total"] == 3
    assert result["by_status"] == {"pending": 0, "sent": 2, "failed": 1, "skipped": 0}
    assert result["by_type"] == {"email": 2, "sms": 1}


# ---------------------------------------------------------------------------
# generate_operational_summary
# ---------------------------------------------------------------------------


def test_operational_summary(service, mock_calendar_repo, mock_doctor_repo):
    """Returns operational metrics for a period."""
    mock_doc = MagicMock()
    mock_doc.service_active = True
    mock_doctor_repo.list_all.return_value = [mock_doc]

    mock_cal = MagicMock()
    mock_cal.status = "approved"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal
    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver
    mock_calendar_repo.list_assignments.return_value = [MagicMock()]
    mock_calendar_repo.list_gaps.return_value = [MagicMock(), MagicMock()]

    result = service.generate_operational_summary(2026, 4)
    assert result["active_doctors"] == 1
    assert result["calendar_status"] == "approved"
    assert result["total_assignments"] == 1
    assert result["unresolved_gaps"] == 2


def test_operational_summary_no_calendar(service, mock_calendar_repo, mock_doctor_repo):
    """When no calendar exists, returns zero counts."""
    mock_doctor_repo.list_all.return_value = []
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_operational_summary(2026, 4)
    assert result["active_doctors"] == 0
    assert result["calendar_status"] is None
    assert result["total_assignments"] == 0
    assert result["unresolved_gaps"] == 0


# ---------------------------------------------------------------------------
# generate_coverage
# ---------------------------------------------------------------------------


def test_coverage_basic(service, mock_calendar_repo, mock_doctor_repo):
    """Basic coverage report with one area and month."""
    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]
    mock_calendar_repo.get_calendar_by_period.return_value = None  # no calendar

    result = service.generate_coverage(
        year_start=2026, month_start=4,
        year_end=2026, month_end=4,
    )
    assert result["period_label"] == "4/2026 - 4/2026"
    assert result["overall_coverage_pct"] == 0.0  # no calendar → no coverage
    assert result["total_gaps"] > 0  # all days are gaps


def test_coverage_with_calendar(service, mock_calendar_repo, mock_doctor_repo):
    """Coverage counts covered days when calendar exists."""
    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]

    # Calendar exists
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal
    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.service_area_id = "area-1"
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.service_date = date(2026, 4, 1)
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    result = service.generate_coverage(
        year_start=2026, month_start=4,
        year_end=2026, month_end=4,
    )
    # April has 30 days, 1 covered → 29 uncovered
    assert result["total_gaps"] == 29
    assert len(result["by_area"]) == 1


def test_coverage_with_area_filter(service, mock_calendar_repo, mock_doctor_repo):
    """Filter by area name narrows results."""
    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_coverage(
        year_start=2026, month_start=4,
        year_end=2026, month_end=4,
        area="Emergencia",
    )
    assert result["overall_coverage_pct"] == 0.0


def test_coverage_with_doctor_filters(service, mock_calendar_repo, mock_doctor_repo):
    """Filters by rank/sex/department narrow coverage scope."""
    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]
    mock_calendar_repo.get_calendar_by_period.return_value = None

    mock_doctor_repo.list_with_filters.return_value = []

    result = service.generate_coverage(
        year_start=2026, month_start=4,
        year_end=2026, month_end=4,
        rank_id="rank-1",
    )
    assert result["overall_coverage_pct"] == 0.0
    mock_doctor_repo.list_with_filters.assert_called_once_with(
        rank_id="rank-1", sex=None, department_id=None, active_only=True
    )


def test_coverage_multi_month(service, mock_calendar_repo, mock_doctor_repo):
    """Coverage spans multiple months."""
    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]
    mock_calendar_repo.get_calendar_by_period.return_value = None  # no calendar → all gaps

    result = service.generate_coverage(
        year_start=2026, month_start=3,
        year_end=2026, month_end=4,
    )
    # March (31) + April (30) = 61 total uncovered days
    assert result["total_gaps"] == 61
    assert result["weakest_day"] is not None  # some day is most gap-heavy


# ---------------------------------------------------------------------------
# generate_workload
# ---------------------------------------------------------------------------


def test_workload_basic(service, mock_calendar_repo, mock_doctor_repo, mock_catalog_repo):
    """Basic workload report with one doctor."""
    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Test"
    mock_doc.rank_id = None
    mock_doc.sex = None
    mock_doc.department_id = None
    mock_doctor_repo.list_with_filters.return_value = [mock_doc]

    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal
    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.service_area_id = "area-1"
    mock_assignment.service_date = date(2026, 4, 1)
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]

    mock_catalog_repo.list_ranks.return_value = []
    mock_catalog_repo.list_departments.return_value = []

    result = service.generate_workload(year=2026, month=4)
    assert result["total_services"] == 1
    assert result["active_doctors"] == 1
    assert len(result["entries"]) == 1
    assert result["entries"][0]["name"] == "Dr. Test"


def test_workload_empty(service, mock_calendar_repo, mock_doctor_repo):
    """Workload with no doctors returns zero counts."""
    mock_doctor_repo.list_with_filters.return_value = []
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_workload(year=2026, month=4)
    assert result["total_services"] == 0
    assert result["active_doctors"] == 0
    assert result["entries"] == []


def test_workload_with_filters(service, mock_calendar_repo, mock_doctor_repo, mock_catalog_repo):
    """Workload with area, order_by, and rank filters."""
    mock_doctor_repo.list_with_filters.return_value = []
    mock_calendar_repo.get_calendar_by_period.return_value = None

    result = service.generate_workload(
        year=2026, month=4,
        area="Emergencia", order_by="alpha",
    )
    assert result["total_services"] == 0


# ---------------------------------------------------------------------------
# generate_doctor_dossier
# ---------------------------------------------------------------------------


def test_doctor_dossier_basic(service, mock_calendar_repo, mock_doctor_repo, mock_mission_repo, mock_catalog_repo):
    """Full doctor dossier with services, missions, restrictions."""
    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Test"
    mock_doc.rank_id = "rank-1"
    mock_doc.sex = "male"
    mock_doc.department_id = "dept-1"
    mock_doc.service_active = True
    mock_doctor_repo.get_by_id.return_value = mock_doc
    mock_doctor_repo.get_allowed_areas.return_value = ["area-1"]
    mock_doctor_repo.list_restrictions.return_value = []
    mock_doctor_repo.get_availability.return_value = None

    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]

    # Only return a calendar for month 4 (the dossier iterates months 1-12)
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    def _calendar_for_period(y, m):
        return mock_cal if m == 4 else None
    mock_calendar_repo.get_calendar_by_period.side_effect = _calendar_for_period
    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.service_date = date(2026, 4, 1)
    mock_assignment.service_area_id = "area-1"
    mock_assignment.assignment_source = "manual"
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    mock_catalog_repo.get_rank_by_id.return_value = None
    mock_catalog_repo.get_department_by_id.return_value = None

    mock_mission_repo.list_participations_for_doctor_in_range.return_value = []

    result = service.generate_doctor_dossier(
        "doc-1",
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
    )
    assert result["name"] == "Dr. Test"
    assert result["total_services"] == 1
    assert len(result["services"]) == 1


def test_doctor_dossier_not_found(service, mock_doctor_repo):
    """Raises ValueError when doctor does not exist."""
    mock_doctor_repo.get_by_id.return_value = None
    with pytest.raises(ValueError, match="Médico no encontrado"):
        service.generate_doctor_dossier("invalid-id")


def test_doctor_dossier_no_period(service, mock_calendar_repo, mock_doctor_repo, mock_mission_repo, mock_catalog_repo):
    """Dossier without date range still works."""
    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Minimal"
    mock_doc.rank_id = None
    mock_doc.sex = None
    mock_doc.department_id = None
    mock_doc.service_active = True
    mock_doctor_repo.get_by_id.return_value = mock_doc
    mock_doctor_repo.get_allowed_areas.return_value = []
    mock_doctor_repo.list_restrictions.return_value = []
    mock_doctor_repo.get_availability.return_value = None

    mock_calendar_repo.list_service_areas.return_value = []

    result = service.generate_doctor_dossier("doc-1")
    assert result["name"] == "Dr. Minimal"
    assert result["total_services"] == 0


# ---------------------------------------------------------------------------
# build_weekly_schedule
# ---------------------------------------------------------------------------


def test_build_weekly_schedule_pdf(service, mock_calendar_repo, mock_doctor_repo):
    """build_weekly_schedule returns PDF bytes."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_cal.month = 4
    mock_cal.year = 2026
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal

    mock_ver = MagicMock()
    mock_ver.id = "ver-1"
    mock_calendar_repo.get_latest_version.return_value = mock_ver

    mock_assignment = MagicMock()
    mock_assignment.doctor_id = "doc-1"
    mock_assignment.service_area_id = "area-1"
    mock_assignment.service_date = date(2026, 4, 1)
    mock_calendar_repo.list_assignments.return_value = [mock_assignment]

    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.name = "Dr. Test"
    mock_doctor_repo.list_all.return_value = [mock_doc]

    mock_sa = MagicMock()
    mock_sa.id = "area-1"
    mock_sa.display_name = "Emergencia"
    mock_calendar_repo.list_service_areas.return_value = [mock_sa]

    result = service.build_weekly_schedule(year=2026, month=4)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_build_weekly_schedule_nonexistent_calendar(service, mock_calendar_repo):
    """Raises ValueError when calendar does not exist."""
    mock_calendar_repo.get_calendar_by_period.return_value = None

    with pytest.raises(ValueError, match="Calendario no encontrado"):
        service.build_weekly_schedule(year=2026, month=4)


def test_build_weekly_schedule_no_assignments(service, mock_calendar_repo):
    """Raises ValueError when no assignments exist."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal
    mock_calendar_repo.get_latest_version.return_value = None

    with pytest.raises(ValueError, match="Versión del calendario no encontrada"):
        service.build_weekly_schedule(year=2026, month=4)


def test_build_weekly_schedule_with_version_id(service, mock_calendar_repo, mock_doctor_repo):
    """Uses explicit version_id when provided."""
    mock_cal = MagicMock()
    mock_cal.id = "cal-1"
    mock_calendar_repo.get_calendar_by_period.return_value = mock_cal

    mock_ver = MagicMock()
    mock_ver.id = "custom-ver"
    mock_calendar_repo.get_version_by_id.return_value = mock_ver

    mock_calendar_repo.list_assignments.return_value = []
    mock_doctor_repo.list_all.return_value = []
    mock_calendar_repo.list_service_areas.return_value = []

    with pytest.raises(ValueError, match="No hay asignaciones"):
        service.build_weekly_schedule(year=2026, month=4, calendar_version_id="custom-ver")

    mock_calendar_repo.get_version_by_id.assert_called_once_with("custom-ver")
