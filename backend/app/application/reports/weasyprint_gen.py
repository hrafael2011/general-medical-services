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
from datetime import datetime
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
# Full Calendar PDF
# ---------------------------------------------------------------------------


def generate_full_calendar_pdf(grid_data: dict) -> bytes:
    """Generate full month calendar grid PDF with premium styling."""
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    month_name = MONTH_NAMES[grid_data["month"] - 1]
    title = f"CALENDARIO DE SERVICIOS — {month_name.upper()} {grid_data['year']}"

    context = {
        "date_line": date_line,
        "title": title,
        "grid_data": grid_data,
        "logo_data_uri": _get_logo_data_uri(),
        **_signature_context(),
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
