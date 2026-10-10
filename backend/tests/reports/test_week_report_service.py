"""Tests for ReportService weekly and full calendar methods."""
from datetime import date
from unittest.mock import MagicMock

import pytest


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
        MagicMock(id="area1", code="emergencia", display_name="Emergencia"),
    ]
    doctor_repo.list_all.return_value = [
        _doctor("doc1", "LOPEZ, JUAN", "809-555-1234"),
        _doctor("doc2", "CRUZ, MARIA", "829-555-9876"),
    ]

    result = service.build_weekly_schedule(
        year=2026, month=5, week_id="week1",
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_build_weekly_schedule_labels_cross_month_dates():
    """Weekly PDF data labels dates with month names across month boundaries."""
    from backend.app.application.reports.report_service import ReportService

    calendar_repo = MagicMock()
    notification_repo = MagicMock()
    doctor_repo = MagicMock()

    service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=notification_repo,
        doctor_repo=doctor_repo,
    )
    service.generate_weekly_schedule_pdf = MagicMock(return_value=b"%PDF-1.4 test")

    week = MagicMock()
    week.id = "week1"
    week.week_number = 1
    week.label = "1RA SEMANA"
    week.start_date = date(2026, 4, 27)
    week.end_date = date(2026, 5, 3)
    calendar_repo.get_week_by_id.return_value = week

    cal = MagicMock()
    cal.id = "cal1"
    cal.month = 5
    cal.year = 2026
    calendar_repo.get_calendar_by_period.return_value = cal
    calendar_repo.get_latest_version.return_value = MagicMock(id="ver1")

    april_assignment = MagicMock()
    april_assignment.doctor_id = "doc1"
    april_assignment.service_date = date(2026, 4, 27)
    april_assignment.service_area_id = "area1"

    may_assignment = MagicMock()
    may_assignment.doctor_id = "doc1"
    may_assignment.service_date = date(2026, 5, 1)
    may_assignment.service_area_id = "area1"

    calendar_repo.list_assignments.return_value = [april_assignment, may_assignment]
    calendar_repo.list_service_areas.return_value = [
        MagicMock(id="area1", code="emergencia", display_name="Emergencia"),
    ]
    doctor_repo.list_all.return_value = [MagicMock(id="doc1", name="LOPEZ, JUAN")]

    service.build_weekly_schedule(year=2026, month=5, week_id="week1")

    schedule_data = service.generate_weekly_schedule_pdf.call_args.args[0]
    assert [day["date_label"] for day in schedule_data] == ["abril 27", "mayo 1"]


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
        MagicMock(id="area1", code="emergencia", display_name="Emergencia"),
        MagicMock(id="area2", code="pista", display_name="Pista"),
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


# ---------------------------------------------------------------------------
# Weekly list — WHATSAPP / CEL column (spec 2026-10-09)
# ---------------------------------------------------------------------------


def _doctor(doctor_id: str, name: str, phone: str | None) -> MagicMock:
    """Build a doctor double with a real `.name` attribute.

    `name` has to be assigned after construction: passing `name=` to MagicMock sets the
    mock's own name, so `doctor.name` would return a child mock and leak its repr into
    the rendered PDF.
    """
    doctor = MagicMock(id=doctor_id)
    doctor.name = name
    doctor.whatsapp_phone = phone
    return doctor


def _service_for_week_one(doctor: MagicMock):
    """ReportService wired to a single-assignment week (2026-05, week1)."""
    from backend.app.application.reports.report_service import ReportService

    calendar_repo = MagicMock()
    doctor_repo = MagicMock()

    week = MagicMock()
    week.id = "week1"
    week.label = "1RA SEMANA"
    week.start_date = date(2026, 5, 4)
    week.end_date = date(2026, 5, 10)
    calendar_repo.get_week_by_id.return_value = week

    cal = MagicMock()
    cal.id = "cal1"
    cal.month = 5
    cal.year = 2026
    calendar_repo.get_calendar_by_period.return_value = cal
    calendar_repo.get_latest_version.return_value = MagicMock(id="ver1")

    assignment = MagicMock()
    assignment.doctor_id = "doc1"
    assignment.service_date = date(2026, 5, 5)
    assignment.service_area_id = "area1"
    calendar_repo.list_assignments.return_value = [assignment]
    calendar_repo.list_service_areas.return_value = [
        MagicMock(id="area1", code="emergencia", display_name="Emergencia"),
    ]

    doctor_repo.list_all.return_value = [doctor]

    service = ReportService(
        calendar_repo=calendar_repo,
        notification_repo=MagicMock(),
        doctor_repo=doctor_repo,
    )
    return service, calendar_repo


def _weekly_payload(doctor: MagicMock) -> dict:
    """Run build_weekly_schedule with the generator mocked and return one assignment."""
    service, _ = _service_for_week_one(doctor)
    service.generate_weekly_schedule_pdf = MagicMock(return_value=b"%PDF-1.4 test")

    service.build_weekly_schedule(year=2026, month=5, week_id="week1")

    schedule_data = service.generate_weekly_schedule_pdf.call_args.args[0]
    return schedule_data[0]["assignments"][0]


def test_weekly_schedule_payload_includes_whatsapp_phone():
    """The doctor's WhatsApp number reaches the template payload."""
    assignment = _weekly_payload(_doctor("doc1", "LOPEZ, JUAN", "809-555-1234"))

    assert assignment["whatsapp_phone"] == "809-555-1234"
    assert assignment["rank_name"] == "LOPEZ, JUAN"
    assert assignment["location"] == "Emergencia"


@pytest.mark.parametrize("raw", ["0000000000", "", "   ", None])
def test_weekly_schedule_blanks_unusable_phone(raw):
    """The migration placeholder and empty values are printed as an empty cell."""
    assignment = _weekly_payload(_doctor("doc1", "LOPEZ, JUAN", raw))

    assert assignment["whatsapp_phone"] == ""


def test_clean_phone_rejects_placeholder_and_non_strings():
    """_clean_phone only lets a real, printable phone number through."""
    from backend.app.application.reports.report_service import _clean_phone

    assert _clean_phone("809-555-1234") == "809-555-1234"
    assert _clean_phone("  809-555-1234  ") == "809-555-1234"
    assert _clean_phone("0000000000") == ""
    assert _clean_phone("") == ""
    assert _clean_phone("   ") == ""
    assert _clean_phone(None) == ""
    # A test double must never leak its repr into the document.
    assert _clean_phone(MagicMock()) == ""


def test_weekly_template_renders_whatsapp_column():
    """The weekly template renders the WHATSAPP / CEL column with the number."""
    from backend.app.application.reports.weasyprint_gen import _env

    html = _env.get_template("weekly_schedule.html").render(
        date_line="MAYO 9 , 2026",
        month_name="Mayo",
        year=2026,
        week_label="1RA SEMANA",
        schedule_data=[
            {
                "day_name": "LUNES",
                "day_number": 5,
                "date_label": "mayo 5",
                "assignments": [
                    {
                        "rank_name": "LOPEZ, JUAN",
                        "whatsapp_phone": "809-555-1234",
                        "location": "Emergencia",
                    },
                    {
                        "rank_name": "CRUZ, MARIA",
                        "whatsapp_phone": "",
                        "location": "Pista",
                    },
                ],
            }
        ],
    )

    assert "WHATSAPP / CEL" in html
    assert "809-555-1234" in html
    assert "LOPEZ, JUAN" in html
    # The old three columns must survive.
    assert "DÍAS" in html
    assert "RANGO / NOMBRE" in html
    assert "LUGAR SERV." in html


def test_weekly_sizing_is_scoped_and_does_not_leak_to_other_reports():
    """The bigger weekly type is scoped to its own page class.

    base.html is shared by coverage, workload and doctor_list, so a sizing rule
    added unscoped there would silently resize the other three PDFs.
    """
    from pathlib import Path

    from backend.app.application.reports.weasyprint_gen import _env

    html = _env.get_template("weekly_schedule.html").render(
        date_line="AGOSTO 9 , 2026",
        month_name="Agosto",
        year=2026,
        week_label="1RA SEMANA",
        schedule_data=[],
    )

    assert "page--weekly-list" in html
    for rule in (
        ".page--weekly-list table { font-size: 8.5pt; }",
        ".page--weekly-list thead th { font-size: 8pt; padding: 4px 9px; }",
        ".page--weekly-list tbody td { font-size: 8.5pt; padding: 3px 9px; }",
        ".page--weekly-list .day-cell { font-size: 9pt; }",
        ".page--weekly-list .signature-block { margin-top: 60px; }",
        ".page--weekly-list .header-logo { height: 96px; }",
    ):
        assert rule in html, f"falta la regla: {rule}"

    templates_dir = Path(_env.loader.searchpath[0])
    for sibling in ("coverage.html", "workload.html", "doctor_list.html"):
        source = (templates_dir / sibling).read_text(encoding="utf-8")
        assert "extra_styles" not in source, f"{sibling} sobrescribe los estilos base"
        assert "page_class" not in source, f"{sibling} usa la clase del semanal"


def test_weekly_schedule_passes_the_exporting_user_to_the_signature():
    """The signer travels from build_weekly_schedule down to the PDF generator."""
    service, _ = _service_for_week_one(_doctor("doc1", "LOPEZ, JUAN", "809-555-1234"))
    captured: dict = {}
    service.generate_weekly_schedule_pdf = MagicMock(
        side_effect=lambda *args, **kwargs: captured.update(kwargs) or b"%PDF-1.4 test"
    )

    service.build_weekly_schedule(
        year=2026, month=5, week_id="week1", signer_name="Rafael Hendrick"
    )

    assert captured["signer_name"] == "Rafael Hendrick"


def test_weekly_schedule_without_a_user_does_not_pass_a_signer():
    """Background exports keep working: no signer means the stored/default name."""
    service, _ = _service_for_week_one(_doctor("doc1", "LOPEZ, JUAN", "809-555-1234"))
    captured: dict = {}
    service.generate_weekly_schedule_pdf = MagicMock(
        side_effect=lambda *args, **kwargs: captured.update(kwargs) or b"%PDF-1.4 test"
    )

    service.build_weekly_schedule(year=2026, month=5, week_id="week1")

    assert captured["signer_name"] is None
