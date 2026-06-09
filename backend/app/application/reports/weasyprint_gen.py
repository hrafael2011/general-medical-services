"""
PDF generation via WeasyPrint with premium HTML/CSS templates.

Replaces the ReportLab-based pdf_templates.py with modern,
print-optimized HTML templates styled with IBM Plex fonts,
Navy+Gold institutional palette, and professional layout.
"""

import base64
import io
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "static", "logo.png")

# ---------------------------------------------------------------------------
# Signature defaults (mirrored from pdf_templates.py)
# ---------------------------------------------------------------------------


@dataclass
class SignatureConfig:
    left_name: str
    left_title1: str
    left_title2: str
    left_title3: str
    right_name: str
    right_title1: str
    right_title2: str
    right_title3: str


DEFAULT_SIGNATURES = SignatureConfig(
    left_name="Dra. MIGUELINA A. ACOSTA RAMOS",
    left_title1="Sargento Médico FARD.",
    left_title2="Encargada de los Servicios de los Médicos Generales",
    left_title3='del Hosp. Mil. Univ. Doc. FARD, "DRL".',
    right_name="ING. CARLOS J. ENCARNACION GONZALEZ",
    right_title1="1er Tt. Ingeniero en Sistema FARD.",
    right_title2="Encargado del Departamento Administrativo de la",
    right_title3='Sub Dirección de Recursos Humanos del Hosp. Mil. Univ. Doc. FARD, "DRL".',
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _get_logo_path() -> str | None:
    """Return absolute logo file path for use in HTML templates, or None."""
    path = os.path.abspath(_LOGO_PATH)
    if os.path.isfile(path):
        return path
    return None


def _get_logo_data_uri() -> str | None:
    """Return logo as base64 data URI for embedding in HTML, or None."""
    logo_path = _get_logo_path()
    if logo_path:
        try:
            with open(logo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(logo_path)[1].lower().lstrip(".")
            mime = "image/png" if ext == "png" else "image/jpeg"
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None
    return None


def _signature_context(sig: SignatureConfig | None = None) -> dict[str, str]:
    cfg = sig or DEFAULT_SIGNATURES
    return {
        "sig_left_name": cfg.left_name,
        "sig_left_title1": cfg.left_title1,
        "sig_left_title2": cfg.left_title2,
        "sig_left_title3": cfg.left_title3,
        "sig_right_name": cfg.right_name,
        "sig_right_title1": cfg.right_title1,
        "sig_right_title2": cfg.right_title2,
        "sig_right_title3": cfg.right_title3,
    }


def _render_to_pdf(template_name: str, context: dict[str, Any]) -> bytes:
    """Render a Jinja2 template and convert to PDF via WeasyPrint."""
    template = _env.get_template(template_name)
    context.setdefault("logo_path", _get_logo_path())
    context.setdefault("logo_data_uri", _get_logo_data_uri())
    html_str = template.render(context)
    return HTML(string=html_str).write_pdf()


# ---------------------------------------------------------------------------
# Weekly Schedule PDF
# ---------------------------------------------------------------------------


def generate_weekly_schedule_pdf(
    schedule_data: list[dict],
    week_label: str,
    month: int,
    year: int,
    date_str: str | None = None,
    signatures: SignatureConfig | None = None,
) -> bytes:
    """Generate a weekly schedule PDF with premium Navy+Gold design.

    Args:
        schedule_data: [{"day_name": "LUNES", "day_number": 27, "assignments": [...]}]
        week_label: e.g. "1RA SEMANA"
        month: 1-12
        year: e.g. 2026
        date_str: override date line
    """
    month_name = MONTH_NAMES[month - 1]

    if date_str is None:
        date_str = f"{month_name.upper()} {datetime.now().day} , {year}"

    context = {
        "date_line": date_str,
        "month_name": month_name,
        "year": year,
        "week_label": week_label,
        "schedule_data": schedule_data,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(signatures),
    }

    return _render_to_pdf("weekly_schedule.html", context)


# ---------------------------------------------------------------------------
# Doctor List PDF (Telegram export)
# ---------------------------------------------------------------------------


def generate_doctor_list_pdf(
    doctors: list[dict],
    title: str,
    subtitle: str = "",
    columns: list[str] | None = None,
    col_widths: list[float] | None = None,
    signatures: SignatureConfig | None = None,
) -> bytes:
    """Generate a generic doctor listing PDF with premium styling."""
    if columns is None:
        columns = ["#", "RANGO", "NOMBRE", "Área"]

    date_line = subtitle or datetime.now().strftime("%d/%m/%Y")

    context = {
        "date_line": date_line,
        "title": title,
        "doctors": doctors,
        "columns": columns,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(signatures),
    }

    return _render_to_pdf("doctor_list.html", context)


# ---------------------------------------------------------------------------
# Coverage Report PDF
# ---------------------------------------------------------------------------


def generate_coverage_pdf(data: dict) -> bytes:
    """Generate coverage report PDF with premium styling."""
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    context = {
        "date_line": date_line,
        "title": f"REPORTE DE COBERTURA - {data['period_label']}",
        "data": data,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(),
    }

    return _render_to_pdf("coverage.html", context)


# ---------------------------------------------------------------------------
# Workload Report PDF
# ---------------------------------------------------------------------------


def generate_workload_pdf(data: dict) -> bytes:
    """Generate workload report PDF with premium styling."""
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    def _sex_label(value: str | None) -> str:
        if value == "male":
            return "Masculino"
        if value == "female":
            return "Femenino"
        return value or "—"

    context = {
        "date_line": date_line,
        "title": f"CARGA DE TRABAJO - {data['period_label']}",
        "data": data,
        "sex_label": _sex_label,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(),
    }

    return _render_to_pdf("workload.html", context)


# ---------------------------------------------------------------------------
# Calendar grid helper
# ---------------------------------------------------------------------------


def _build_calendar_weeks(grid_data: dict) -> list[list[dict | None]]:
    """Build a calendar matrix: list of weeks, each week is 7 day slots (Sun-Sat).

    Uses the same rule as compute_weeks: includes every Sunday-Saturday week
    that contains at least one day of the target month. Days from adjacent
    months use real assignments from adjacent_cells.

    Each day slot is either None or:
    {
        "day": int,
        "day_name": str,
        "assignments": [{"area": str, "doctor": str, "doctor_rank": str}, ...],
        "is_current_month": bool,
    }
    """
    from calendar import monthrange
    from datetime import timedelta

    month = grid_data["month"]
    year = grid_data["year"]
    last_day = monthrange(year, month)[1]

    # Build lookup: day_number -> {day_name, cells}
    rows_by_day: dict[int, dict] = {}
    for row in grid_data["rows"]:
        rows_by_day[row["day"]] = row

    areas = grid_data.get("areas", [])
    area_codes = grid_data.get("area_codes", [])
    adjacent_cells = grid_data.get("adjacent_cells", {})  # "YYYY-MM-DD" -> area_code -> doctor_info

    # English weekday name for adjacent-month day labels
    _DAY_ES = {
        "Monday": "LUNES", "Tuesday": "MARTES", "Wednesday": "MIÉRCOLES",
        "Thursday": "JUEVES", "Friday": "VIERNES", "Saturday": "SÁBADO", "Sunday": "DOMINGO",
    }

    # Find first Sunday ≤ 1st of month (same rule as compute_weeks)
    first_day_dt = date(year, month, 1)
    days_since_sunday = (first_day_dt.weekday() + 1) % 7
    current_sunday = first_day_dt - timedelta(days=days_since_sunday)

    weeks: list[list[dict | None]] = []

    while True:
        current_saturday = current_sunday + timedelta(days=6)
        # Stop when the week no longer contains ANY day of the target month
        if current_sunday.month != month and current_saturday.month != month:
            break

        week_days: list[dict | None] = []
        for i in range(7):
            d = current_sunday + timedelta(days=i)
            is_current = d.month == month
            if is_current and 1 <= d.day <= last_day:
                row = rows_by_day.get(d.day, {"day": d.day, "day_name": "", "cells": {}})
                cells = row.get("cells", {})
                assignments = []
                for area in areas:
                    cell_value = cells.get(area, {"name": "—", "rank": ""})
                    if isinstance(cell_value, str):
                        cell_value = {"name": cell_value, "rank": ""}
                    assignments.append({
                        "area": area,
                        "doctor": cell_value["name"],
                        "doctor_rank": cell_value["rank"],
                    })
                week_days.append({
                    "day": d.day,
                    "day_name": row.get("day_name", d.strftime("%A").upper()),
                    "assignments": assignments,
                    "is_current_month": True,
                })
            else:
                # Adjacent-month day: look up real assignments from the adjacent month's calendar
                date_str = d.isoformat()
                day_cells = adjacent_cells.get(date_str, {})
                adjacent_assignments = []
                for idx, area in enumerate(areas):
                    area_code = area_codes[idx] if idx < len(area_codes) else area
                    cell_value = day_cells.get(area_code)
                    if cell_value:
                        adjacent_assignments.append({
                            "area": area,
                            "doctor": cell_value["name"],
                            "doctor_rank": cell_value["rank"],
                        })
                    else:
                        adjacent_assignments.append({
                            "area": area,
                            "doctor": "—",
                            "doctor_rank": "",
                        })
                week_days.append({
                    "day": d.day,
                    "day_name": _DAY_ES.get(d.strftime("%A"), d.strftime("%A").upper()),
                    "assignments": adjacent_assignments,
                    "is_current_month": False,
                })
        weeks.append(week_days)
        current_sunday += timedelta(days=7)

    return weeks


# ---------------------------------------------------------------------------
# Area color mapping (mirrors frontend AREA_COLOR_MAP)
# ---------------------------------------------------------------------------

_AREA_COLORS: dict[str, str] = {
    "Emergencia": "#dc2626",
    "Pista": "#2563eb",
    "Disponible": "#16a34a",
}


def _resolve_area_color(area_name: str) -> str:
    """Return the color for a given area display name."""
    return _AREA_COLORS.get(area_name, "#6b7280")


# ---------------------------------------------------------------------------
# Full Calendar PDF
# ---------------------------------------------------------------------------


def generate_full_calendar_pdf(grid_data: dict) -> bytes:
    """Generate full month calendar grid PDF with premium styling.

    Renders a real calendar layout (7 columns Mon-Sun) with doctor
    assignments in each day cell. No signature block.
    """
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    month_name = MONTH_NAMES[grid_data["month"] - 1]
    title = f"CALENDARIO DE SERVICIOS — {month_name.upper()} {grid_data['year']}"

    calendar_weeks = _build_calendar_weeks(grid_data)
    areas = grid_data.get("areas", [])
    summary = grid_data.get("summary", {})

    # Build color map for all areas in this calendar
    area_colors = {a: _resolve_area_color(a) for a in areas}

    context = {
        "date_line": date_line,
        "title": title,
        "calendar_weeks": calendar_weeks,
        "areas": areas,
        "area_colors": area_colors,
        "summary": summary,
        "month": grid_data["month"],
        "year": grid_data["year"],
        "logo_data_uri": _get_logo_data_uri(),
        "logo_path": _get_logo_path(),
        "day_names": ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"],
    }

    return _render_to_pdf("full_calendar.html", context)


# ---------------------------------------------------------------------------
# Doctor Dossier PDF (Portrait A4)
# ---------------------------------------------------------------------------


def generate_dossier_pdf(data: dict) -> bytes:
    """Generate doctor dossier PDF (portrait A4) with premium styling."""
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    context = {
        "date_line": date_line,
        "title": "FICHA DE SERVICIO MÉDICO",
        "data": data,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(),
    }

    return _render_to_pdf("dossier.html", context)
