"""Tests for PDF template functions (pure PDF generation)."""

from datetime import date
from unittest.mock import patch

import pytest

from backend.app.application.reports.pdf_templates import (
    _sex_label,
    generate_coverage_pdf,
    generate_doctor_list_pdf,
    generate_dossier_pdf,
    generate_weekly_schedule_pdf,
    generate_workload_pdf,
)


# ---------------------------------------------------------------------------
# _sex_label helper
# ---------------------------------------------------------------------------


def test_sex_label_male() -> None:
    assert _sex_label("male") == "Masculino"


def test_sex_label_female() -> None:
    assert _sex_label("female") == "Femenino"


def test_sex_label_none() -> None:
    assert _sex_label(None) is None


def test_sex_label_unknown() -> None:
    assert _sex_label("other") == "other"


# ---------------------------------------------------------------------------
# generate_doctor_list_pdf
# ---------------------------------------------------------------------------


def test_doctor_list_pdf_returns_bytes() -> None:
    result = generate_doctor_list_pdf(
        doctors=[{"name": "Dr. Test", "rank": "Cabo"}],
        title="Lista de Médicos",
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_doctor_list_pdf_empty_doctors() -> None:
    result = generate_doctor_list_pdf(
        doctors=[],
        title="Empty List",
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_doctor_list_pdf_custom_columns() -> None:
    doctors = [
        {"name": "Dr. A", "rank": "Cabo", "department": "Emergencia"},
        {"name": "Dr. B", "rank": "Sargento", "department": "Pista"},
    ]
    result = generate_doctor_list_pdf(
        doctors=doctors,
        title="Médicos",
        columns=["#", "RANGO", "NOMBRE", "Área"],
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_doctor_list_pdf_default_columns() -> None:
    doctors = [{"name": "Dr. C", "rank": "Teniente"}]
    result = generate_doctor_list_pdf(doctors=doctors, title="Test")
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# generate_weekly_schedule_pdf
# ---------------------------------------------------------------------------


def test_weekly_schedule_pdf_returns_bytes() -> None:
    schedule = [
        {
            "day_name": "LUNES",
            "day_number": 1,
            "assignments": [
                {"rank_name": "CABO PEREZ", "location": "EMERGENCIA"},
            ],
        },
    ]
    result = generate_weekly_schedule_pdf(
        schedule_data=schedule,
        week_label="1RA SEMANA",
        month=4,
        year=2026,
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_weekly_schedule_pdf_multiple_days() -> None:
    schedule = [
        {
            "day_name": "LUNES",
            "day_number": 1,
            "assignments": [
                {"rank_name": "DR. A", "location": "EMERGENCIA"},
                {"rank_name": "DR. B", "location": "PISTA"},
            ],
        },
        {
            "day_name": "MARTES",
            "day_number": 2,
            "assignments": [
                {"rank_name": "DR. C", "location": "DISPONIBLE"},
            ],
        },
    ]
    result = generate_weekly_schedule_pdf(
        schedule_data=schedule,
        week_label="2DA SEMANA",
        month=5,
        year=2026,
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_weekly_schedule_pdf_empty_assignments() -> None:
    schedule = [
        {
            "day_name": "LUNES",
            "day_number": 1,
            "assignments": [],
        },
    ]
    result = generate_weekly_schedule_pdf(
        schedule_data=schedule,
        week_label="TEST",
        month=1,
        year=2026,
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_weekly_schedule_pdf_custom_date_str() -> None:
    schedule = [
        {
            "day_name": "LUNES",
            "day_number": 27,
            "assignments": [
                {"rank_name": "DR. X", "location": "EMERGENCIA"},
            ],
        },
    ]
    result = generate_weekly_schedule_pdf(
        schedule_data=schedule,
        week_label="TEST",
        month=4,
        year=2026,
        date_str="ABRIL 27, 2026",
    )
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# generate_coverage_pdf
# ---------------------------------------------------------------------------


def test_coverage_pdf_returns_bytes() -> None:
    data = {
        "period_label": "04/2026 - 04/2026",
        "overall_coverage_pct": 85.5,
        "total_gaps": 10,
        "most_critical_area": "Emergencia",
        "weakest_day": "Lunes",
        "by_area": [
            {
                "area_name": "Emergencia",
                "days_covered": 25,
                "days_uncovered": 5,
                "coverage_pct": 83.3,
            },
            {
                "area_name": "Pista",
                "days_covered": 30,
                "days_uncovered": 0,
                "coverage_pct": 100.0,
            },
        ],
    }
    result = generate_coverage_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_coverage_pdf_no_by_area() -> None:
    data = {
        "period_label": "04/2026",
        "overall_coverage_pct": 0.0,
        "total_gaps": 0,
        "most_critical_area": None,
        "weakest_day": None,
        "by_area": [],
    }
    result = generate_coverage_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# generate_workload_pdf
# ---------------------------------------------------------------------------


def test_workload_pdf_returns_bytes() -> None:
    data = {
        "period_label": "04/2026",
        "total_services": 50,
        "active_doctors": 10,
        "avg_per_doctor": 5.0,
        "most_load": {"name": "Dr. A", "total": 10},
        "least_load": {"name": "Dr. B", "total": 2},
        "entries": [
            {
                "name": "Dr. A",
                "rank": "Cabo",
                "sex": "male",
                "department": "Emergencia",
                "emergencia": 8,
                "pista": 1,
                "disponible": 1,
                "total": 10,
            },
            {
                "name": "Dr. B",
                "rank": "Sargento",
                "sex": "female",
                "department": "Pista",
                "emergencia": 0,
                "pista": 2,
                "disponible": 0,
                "total": 2,
            },
        ],
    }
    result = generate_workload_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_workload_pdf_empty_entries() -> None:
    data = {
        "period_label": "04/2026",
        "total_services": 0,
        "active_doctors": 0,
        "avg_per_doctor": 0.0,
        "most_load": None,
        "least_load": None,
        "entries": [],
    }
    result = generate_workload_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# generate_dossier_pdf
# ---------------------------------------------------------------------------


def test_dossier_pdf_returns_bytes() -> None:
    data = {
        "name": "Dr. Juan Pérez",
        "rank": "Cabo",
        "sex": "male",
        "department": "Emergencia",
        "areas": ["Emergencia", "Pista"],
        "period_label": "01/04/2026 - 30/04/2026",
        "total_services": 15,
        "services_by_area": {"Emergencia": 10, "Pista": 5},
        "avg_weekly": 3.5,
        "services": [
            {"date": "2026-04-01", "day_name": "Lunes", "area": "Emergencia"},
            {"date": "2026-04-02", "day_name": "Martes", "area": "Pista"},
        ],
        "missions": [
            {"mission": "M001", "role": "leader", "status": "confirmed"},
        ],
        "restrictions": [
            {"type": "licencia", "date": "2026-04-10", "reason": "Personal"},
        ],
        "availability": ["Monday", "Tuesday"],
    }
    result = generate_dossier_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")


def test_dossier_pdf_no_optional_sections() -> None:
    """Dossier without missions, restrictions, or availability."""
    data = {
        "name": "Dr. Minimal",
        "rank": None,
        "sex": None,
        "department": None,
        "areas": [],
        "period_label": "01/04/2026 - 30/04/2026",
        "total_services": 0,
        "services_by_area": {},
        "avg_weekly": 0.0,
        "services": [],
        "missions": [],
        "restrictions": [],
        "availability": [],
    }
    result = generate_dossier_pdf(data)
    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF-")
