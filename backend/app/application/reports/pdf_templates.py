"""
PDF templates for system reports using reportlab.

Generates professional PDFs with institutional header (FARD, Hospital Militar),
logo, styled tables, signature block, and page footer.
All reports use landscape A4 format matching the existing institutional style.
"""

import io
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_LOGO_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "static", "logo.png"
)

# Page dimensions (landscape A4)
PAGE_W, PAGE_H = landscape(A4)
LEFT_M = 1.8 * cm
RIGHT_M = 1.8 * cm
TOP_M = 2.5 * cm
BOTTOM_M = 1.8 * cm
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M

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


# Default values — used when system_settings records are absent.
DEFAULT_SIGNATURES = SignatureConfig(
    left_name='Dra. MIGUELINA A. ACOSTA RAMOS',
    left_title1='Sargento Médico FARD.',
    left_title2='Encargada de los Servicios de los Médicos Generales',
    left_title3='del Hosp. Mil. Univ. Doc. FARD, "DRL".',
    right_name='ING. CARLOS J. ENCARNACION GONZALEZ',
    right_title1='1er Tt. Ingeniero en Sistema FARD.',
    right_title2='Encargado del Departamento Administrativo de la',
    right_title3='Sub Dirección de Recursos Humanos del Hosp. Mil. Univ. Doc. FARD, "DRL".',
)


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------

def _get_logo() -> Image | None:
    """Return logo Image if file exists, else None."""
    path = os.path.abspath(_LOGO_PATH)
    if os.path.isfile(path):
        try:
            img = Image(path, width=3.2 * cm, height=2.8 * cm)
            img.hAlign = "LEFT"
            return img
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Institutional header block
# ---------------------------------------------------------------------------

_HEADER_SUBDIR = "SUBDIRECCIÓN DE RECURSOS HUMANOS"
_HEADER_HOSPITAL = (
    "HOSPITAL MILITAR UNIVERSITARIO DOCENTE, FARD "
    '"DR. RAMÓN DE LARA"'
)
_HEADER_BASE = (
    'BASE AÉREA "SAN ISIDRO", '
    "FUERZA AÉREA DE REPÚBLICA DOMINICANA, "
    "SAN ISIDRO, SANTO DOMINGO ESTE, R.D."
)
_HEADER_LEMA = '"Todo por la Patria"'


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_styles = getSampleStyleSheet()

_STYLE_SUBDIR = ParagraphStyle(
    "SubDir", parent=_styles["Normal"],
    fontSize=8, leading=10, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)

_STYLE_INSTITUCION = ParagraphStyle(
    "Institucion", parent=_styles["Normal"],
    fontSize=9, leading=11, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)

_STYLE_LEMA = ParagraphStyle(
    "Lema", parent=_styles["Normal"],
    fontSize=8, leading=10, alignment=TA_CENTER,
)

_STYLE_DATE = ParagraphStyle(
    "DateLine", parent=_styles["Normal"],
    fontSize=8, leading=10, alignment=TA_LEFT,
)

_STYLE_TITLE = ParagraphStyle(
    "ReportTitle", parent=_styles["Normal"],
    fontSize=10, leading=13, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
    spaceBefore=4, spaceAfter=8,
)

_STYLE_TABLE_HEADER = ParagraphStyle(
    "TableHeader", parent=_styles["Normal"],
    fontSize=7.5, leading=9,
    fontName="Helvetica-Bold",
)

_STYLE_TABLE_CELL = ParagraphStyle(
    "TableCell", parent=_styles["Normal"],
    fontSize=7.5, leading=9,
)

_STYLE_SECTION = ParagraphStyle(
    "Section", parent=_styles["Normal"],
    fontSize=9, leading=11, alignment=TA_LEFT,
    fontName="Helvetica-Bold",
    spaceBefore=6, spaceAfter=4,
)

_STYLE_SIG_NAME = ParagraphStyle(
    "SigName", parent=_styles["Normal"],
    fontSize=7.5, leading=9, alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)

_STYLE_SIG_TITLE = ParagraphStyle(
    "SigTitle", parent=_styles["Normal"],
    fontSize=7, leading=8.5, alignment=TA_CENTER,
)

_STYLE_FOOTER = ParagraphStyle(
    "Footer", parent=_styles["Normal"],
    fontSize=7, textColor=colors.grey, alignment=TA_CENTER,
)


# ---------------------------------------------------------------------------
# Header / footer
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc):
    """Draw the institutional header block and page number."""
    canvas.saveState()
    # Thin separator line below header area
    y_line = PAGE_H - 1.75 * cm
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(0.4)
    canvas.line(LEFT_M, y_line, PAGE_W - RIGHT_M, y_line)
    # Page number
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(PAGE_W / 2, 0.7 * cm, str(doc.page))
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Build story helpers
# ---------------------------------------------------------------------------

def _build_header_story(date_line: str, title: str) -> list[object]:
    """Build the institutional header: logo + text block + date + title."""
    story: list[object] = []

    # Top area: logo on left, header text centered
    logo = _get_logo()
    if logo:
        # We create a table with logo on left and header text on right
        header_text = (
            f"<b>{_HEADER_SUBDIR}</b><br/>"
            f"<b>{_HEADER_HOSPITAL}</b><br/>"
            f"<b>{_HEADER_BASE}</b><br/>"
            f"{_HEADER_LEMA}"
        )
        header_table = Table(
            [[logo, Paragraph(header_text, _STYLE_INSTITUCION)]],
            colWidths=[3.8 * cm, CONTENT_W - 3.8 * cm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (1, 1), (1, 1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        story.append(Paragraph(_HEADER_SUBDIR, _STYLE_SUBDIR))
        story.append(Paragraph(_HEADER_HOSPITAL, _STYLE_INSTITUCION))
        story.append(Paragraph(_HEADER_BASE, _STYLE_INSTITUCION))
        story.append(Paragraph(_HEADER_LEMA, _STYLE_LEMA))

    story.append(Spacer(1, 3 * mm))

    # Date line
    story.append(Paragraph(date_line, _STYLE_DATE))
    story.append(Spacer(1, 2 * mm))

    # Title
    story.append(Paragraph(title, _STYLE_TITLE))

    return story


def _make_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Build a styled table (first row = header, rest = data)."""
    styled_rows: list[list[Paragraph]] = []
    for i, row in enumerate(data):
        style = _STYLE_TABLE_HEADER if i == 0 else _STYLE_TABLE_CELL
        styled_rows.append([Paragraph(str(c), style) for c in row])

    t = Table(styled_rows, colWidths=col_widths, repeatRows=1)
    base_style = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        # Body alternating rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fa")]),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Left/right padding
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(base_style))
    return t


def _build_signature_block(config: SignatureConfig | None = None) -> Table:
    """Build the two-column signature block at the bottom."""
    cfg = config or DEFAULT_SIGNATURES
    left = [
        Paragraph(cfg.left_name, _STYLE_SIG_NAME),
        Paragraph(cfg.left_title1, _STYLE_SIG_TITLE),
        Paragraph(cfg.left_title2, _STYLE_SIG_TITLE),
        Paragraph(cfg.left_title3, _STYLE_SIG_TITLE),
    ]
    right = [
        Paragraph(cfg.right_name, _STYLE_SIG_NAME),
        Paragraph(cfg.right_title1, _STYLE_SIG_TITLE),
        Paragraph(cfg.right_title2, _STYLE_SIG_TITLE),
        Paragraph(cfg.right_title3, _STYLE_SIG_TITLE),
    ]

    # Signature line above each name
    sig_data = [
        [
            Paragraph("___________________________________", _STYLE_SIG_TITLE),
            Paragraph("___________________________________", _STYLE_SIG_TITLE),
        ],
        left,
        right,
    ]

    t = Table(sig_data, colWidths=[CONTENT_W * 0.48, CONTENT_W * 0.48])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _build_doc(title: str, subtitle: str) -> tuple[SimpleDocTemplate, io.BytesIO]:
    """Create a base PDF document (landscape A4)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=LEFT_M,
        rightMargin=RIGHT_M,
        topMargin=TOP_M,
        bottomMargin=BOTTOM_M,
    )
    return doc, buf


# ---------------------------------------------------------------------------
# Weekly schedule report (formato SERVICIOS)
# ---------------------------------------------------------------------------

def generate_weekly_schedule_pdf(
    schedule_data: list[dict],
    week_label: str,
    month: int,
    year: int,
    date_str: str | None = None,
    signatures: SignatureConfig | None = None,
) -> bytes:
    """Generate a weekly schedule PDF matching the SERVICIOS format.

    Args:
        schedule_data: List of day dicts:
            {"day_name": "LUNES", "day_number": 27,
             "assignments": [
                {"rank_name": "CABO PEREZ, JUAN", "location": "EMERGENCIA"},
                ...
             ]}
        week_label: e.g. "1RA SEMANA"
        month: month number (1-12)
        year: year
        date_str: optional date override (e.g. "ABRIL 24 , 2026")
    """
    month_name = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ][month - 1]

    if date_str is None:
        date_str = f"{month_name.upper()} {datetime.now().day} , {year}"

    title = (
        f"LISTA DEL PERSONAL MEDICO GENERAL, QUE SE ENCUENTRA DE SERVICIO "
        f"LOS DÍAS INDICADOS AL LADO DE SUS RESPECTIVOS NOMBRE:"
        f"DEL MES DE {month_name.upper()} DEL AÑO {year}"
    )

    doc, buf = _build_doc(title, date_str)
    story = _build_header_story(date_str, title)
    story.append(Spacer(1, 2 * mm))

    # Weekly schedule table: no traditional header, just data rows
    # Format: day rows span vertically, each person on own line
    schedule_rows: list[list[str]] = []
    header = ["DÍAS", "RANGO / NOMBRE", "LUGAR SERV."]
    schedule_rows.append(header)

    for day_entry in schedule_data:
        day_name = day_entry.get("day_name", "")
        day_number = day_entry.get("day_number", "")
        day_label = f"{day_name} {day_number}" if day_number else day_name
        assignments = day_entry.get("assignments", [])

        for i, assgn in enumerate(assignments):
            rank_name = assgn.get("rank_name", "")
            location = assgn.get("location", "")
            if i == 0:
                schedule_rows.append([day_label, rank_name, location])
            else:
                schedule_rows.append(["", rank_name, location])

    col_widths = [3.2 * cm, 7.5 * cm, 4.5 * cm]
    story.append(_make_table(schedule_rows, col_widths))

    # Signature block
    story.append(Spacer(1, 1.2 * cm))
    story.append(_build_signature_block(signatures))
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Generic doctor listing (used by Telegram for query-to-PDF conversion)
# ---------------------------------------------------------------------------

def generate_doctor_list_pdf(
    doctors: list[dict],
    title: str,
    subtitle: str = "",
    columns: list[str] | None = None,
    col_widths: list[float] | None = None,
    signatures: SignatureConfig | None = None,
) -> bytes:
    """Generate a generic doctor listing PDF (used by Telegram exports).

    Args:
        doctors: List of dicts with keys matching *columns*.
        title: Report title.
        subtitle: Optional subtitle/date line.
        columns: Column header names. Defaults to ["#", "RANGO", "NOMBRE", "Área"].
        col_widths: Column widths. Defaults proportional to page width.
    """
    if columns is None:
        columns = ["#", "RANGO", "NOMBRE", "Área"]
    if col_widths is None:
        col_widths = [1.2 * cm, 4.5 * cm, 6 * cm, 4 * cm]

    date_line = subtitle or datetime.now().strftime("%d/%m/%Y")

    headers = columns
    rows = [headers]
    for doc_data in doctors:
        rows.append([
            str(doc_data.get(col.lower(), doc_data.get(col, "")))
            for col in columns
        ])

    doc, buf = _build_doc(title, date_line)
    story = _build_header_story(date_line, title)
    story.append(Spacer(1, 3 * mm))
    story.append(_make_table(rows, col_widths))
    story.append(Spacer(1, 1.5 * cm))
    story.append(_build_signature_block(signatures))
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Coverage report PDF
# ---------------------------------------------------------------------------


def generate_coverage_pdf(data: dict) -> bytes:
    """Generate a PDF report of coverage and gaps."""
    title = f"REPORTE DE COBERTURA - {data['period_label']}"
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    doc, buf = _build_doc(title, date_line)
    story = _build_header_story(date_line, title)
    story.append(Spacer(1, 3 * mm))

    summary_data = [
        ["Indicador", "Valor"],
        ["% Cobertura General", f"{data['overall_coverage_pct']}%"],
        ["Total Brechas", str(data['total_gaps'])],
        ["Área Más Crítica", data.get('most_critical_area', '—') or '—'],
        ["Día Más Débil", data.get('weakest_day', '—') or '—'],
    ]
    story.append(Paragraph("RESUMEN", _STYLE_SECTION))
    story.append(_make_table(summary_data, col_widths=[6 * cm, 10 * cm]))
    story.append(Spacer(1, 4 * mm))

    headers = ["Área", "Días Cubiertos", "Días Descubiertos", "% Cobertura"]
    col_widths = [4 * cm, 3.5 * cm, 3.5 * cm, 3 * cm]
    rows = [headers]
    for area in data.get("by_area", []):
        rows.append([
            area["area_name"],
            str(area["days_covered"]),
            str(area["days_uncovered"]),
            f"{area['coverage_pct']}%",
        ])

    story.append(Paragraph("COBERTURA POR ÁREA", _STYLE_SECTION))
    story.append(_make_table(rows, col_widths))
    story.append(Spacer(1, 1.5 * cm))
    story.append(_build_signature_block())
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Workload report PDF
# ---------------------------------------------------------------------------


def generate_workload_pdf(data: dict) -> bytes:
    """Generate a PDF report of doctor workload."""
    title = f"CARGA DE TRABAJO - {data['period_label']}"
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    doc, buf = _build_doc(title, date_line)
    story = _build_header_story(date_line, title)
    story.append(Spacer(1, 3 * mm))

    summary_data = [
        ["Indicador", "Valor"],
        ["Total Servicios", str(data['total_services'])],
        ["Médicos Activos", str(data['active_doctors'])],
        ["Promedio por Médico", str(data['avg_per_doctor'])],
        ["Mayor Carga",
         f"{data.get('most_load', {}).get('name', '—')} ({data.get('most_load', {}).get('total', 0)})"],
        ["Menor Carga",
         f"{data.get('least_load', {}).get('name', '—')} ({data.get('least_load', {}).get('total', 0)})"],
    ]
    story.append(Paragraph("RESUMEN", _STYLE_SECTION))
    story.append(_make_table(summary_data, col_widths=[6 * cm, 10 * cm]))
    story.append(Spacer(1, 4 * mm))

    headers = ["Médico", "Rango", "Sexo", "Depto", "Emerg", "Pista", "Disp.", "Total"]
    col_widths = [4 * cm, 2.5 * cm, 1.5 * cm, 2.5 * cm, 1.8 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm]
    rows = [headers]
    for entry in data.get("entries", []):
        rows.append([
            entry["name"],
            entry.get("rank") or "—",
            entry.get("sex") or "—",
            entry.get("department") or "—",
            str(entry.get("emergencia", 0)),
            str(entry.get("pista", 0)),
            str(entry.get("disponible", 0)),
            str(entry["total"]),
        ])

    story.append(Paragraph("DETALLE POR MÉDICO", _STYLE_SECTION))
    story.append(_make_table(rows, col_widths))
    story.append(Spacer(1, 1.5 * cm))
    story.append(_build_signature_block())
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Doctor dossier PDF (portrait A4)
# ---------------------------------------------------------------------------


def generate_dossier_pdf(data: dict) -> bytes:
    """Generate a PDF with full medical dossier (portrait A4)."""
    from reportlab.lib.pagesizes import A4

    title = "FICHA DE SERVICIO MÉDICO"
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT_M,
        rightMargin=RIGHT_M,
        topMargin=TOP_M,
        bottomMargin=BOTTOM_M,
    )
    story = _build_header_story(date_line, title)
    story.append(Spacer(1, 4 * mm))

    section = ParagraphStyle("SectionA4", parent=_STYLE_SECTION, fontSize=10, leading=12)
    cell = ParagraphStyle("CellA4", parent=_STYLE_TABLE_CELL, fontSize=8, leading=10)

    doc_data = [
        ["Nombre", data.get("name", "—")],
        ["Rango", data.get("rank") or "—"],
        ["Sexo", data.get("sex") or "—"],
        ["Departamento", data.get("department") or "—"],
        ["Áreas Habilitadas", ", ".join(data.get("areas", [])) or "—"],
        ["Período", data.get("period_label", "—")],
    ]
    t = Table(
        [[Paragraph(c[0], cell), Paragraph(c[1], cell)] for c in doc_data],
        colWidths=[4 * cm, 12 * cm],
    )
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Paragraph("DATOS DEL MÉDICO", section))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    services_by_area = data.get("services_by_area", {})
    total = data.get("total_services", 0)
    avg = data.get("avg_weekly", 0)
    summary_rows = [
        ["Total Servicios", str(total)],
        ["Promedio Semanal", str(avg)],
    ]
    for area_name, count in services_by_area.items():
        summary_rows.append([f"  - {area_name}", str(count)])

    story.append(Paragraph("RESUMEN DEL PERÍODO", section))
    st = Table(
        [[Paragraph(r[0], cell), Paragraph(r[1], cell)] for r in summary_rows],
        colWidths=[8 * cm, 4 * cm],
    )
    st.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(st)
    story.append(Spacer(1, 4 * mm))

    services = data.get("services", [])
    if services:
        svc_headers = ["Fecha", "Día", "Área"]
        svc_rows = [svc_headers]
        for s in services:
            svc_rows.append([str(s.get("date", "")), str(s.get("day_name", "")), str(s.get("area", ""))])
        story.append(Paragraph("DETALLE DE SERVICIOS", section))
        story.append(_make_table(svc_rows, col_widths=[3.5 * cm, 3.5 * cm, 5 * cm]))
        story.append(Spacer(1, 4 * mm))

    missions = data.get("missions", [])
    if missions:
        miss_headers = ["Misión", "Rol", "Estado"]
        miss_rows = [miss_headers]
        for m in missions:
            miss_rows.append([str(m.get("mission", "")), str(m.get("role", "")), str(m.get("status", ""))])
        story.append(Paragraph("MISIONES EN EL PERÍODO", section))
        story.append(_make_table(miss_rows, col_widths=[5 * cm, 3.5 * cm, 3 * cm]))
        story.append(Spacer(1, 4 * mm))

    restrictions = data.get("restrictions", [])
    if restrictions:
        rest_headers = ["Tipo", "Fecha", "Motivo"]
        rest_rows = [rest_headers]
        for r in restrictions:
            rest_rows.append([str(r.get("type", "")), str(r.get("date") or "—"), str(r.get("reason", ""))])
        story.append(Paragraph("RESTRICCIONES Y LICENCIAS", section))
        story.append(_make_table(rest_rows, col_widths=[3.5 * cm, 3.5 * cm, 5 * cm]))
        story.append(Spacer(1, 4 * mm))

    avail = data.get("availability", [])
    if avail:
        story.append(Paragraph(f"DISPONIBILIDAD DECLARADA: {', '.join(avail)}", section))

    story.append(Spacer(1, 1 * cm))
    story.append(_build_signature_block())
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Full calendar single-page PDF (day x area grid)
# ---------------------------------------------------------------------------


def generate_full_calendar_pdf(grid_data: dict) -> bytes:
    """Generate a single-page landscape PDF with the full month calendar grid.

    Args:
        grid_data: {
            "month": int, "year": int,
            "areas": list[str],
            "rows": [{"day": int, "day_name": str, "cells": {area: doctor_name}}],
            "summary": {"total_services": int, "gaps": int,
                        "active_doctors": int, "coverage_pct": int},
        }
    """
    month_names = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    month_name = month_names[grid_data["month"] - 1]
    title = f"CALENDARIO DE SERVICIOS — {month_name.upper()} {grid_data['year']}"
    date_line = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    # Tighter margins for the grid to fit on one page
    tight_left = 1.2 * cm
    tight_right = 1.2 * cm
    tight_top = 2.0 * cm
    tight_bottom = 1.2 * cm
    tight_content_w = PAGE_W - tight_left - tight_right

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=tight_left,
        rightMargin=tight_right,
        topMargin=tight_top,
        bottomMargin=tight_bottom,
    )

    story = _build_header_story(date_line, title)
    story.append(Spacer(1, 2 * mm))

    # Summary line
    s = grid_data["summary"]
    summary_text = (
        f"Total Servicios: {s['total_services']} | "
        f"Huecos: {s['gaps']} | "
        f"Medicos Activos: {s['active_doctors']} | "
        f"Cobertura: {s['coverage_pct']}%"
    )
    story.append(Paragraph(summary_text, _STYLE_SECTION))
    story.append(Spacer(1, 2 * mm))

    # Build grid
    areas = grid_data["areas"]
    headers = ["Dia", "Dia Sem."] + areas
    table_rows = [headers]

    for row in grid_data["rows"]:
        day_str = str(row["day"])
        day_name = row["day_name"][:3]  # LUN, MAR, MIE...
        cells = [day_str, day_name]
        for area in areas:
            cells.append(row["cells"].get(area, "—"))
        table_rows.append(cells)

    # Dynamic column widths
    n_areas = max(len(areas), 1)
    area_col_w = (tight_content_w - 2.2 * cm) / n_areas
    col_widths = [1.0 * cm, 1.2 * cm] + [area_col_w] * n_areas

    # Build styled paragraphs for table
    styled_rows: list[list[Paragraph]] = []
    for i, row in enumerate(table_rows):
        style = _STYLE_TABLE_HEADER if i == 0 else _STYLE_TABLE_CELL
        styled_rows.append([Paragraph(str(c), style) for c in row])

    t = Table(styled_rows, colWidths=col_widths, repeatRows=1)
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bdc3c7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
    ]

    # Weekend highlighting
    for i, row in enumerate(grid_data["rows"], start=1):
        day_name = row.get("day_name", "")
        if day_name in ("SABADO", "DOMINGO"):
            table_style_cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f0f0f0")))

    # Gap highlighting
    for i, row in enumerate(grid_data["rows"], start=1):
        for j, area in enumerate(areas, start=2):
            if row["cells"].get(area) == "—":
                table_style_cmds.append(
                    ("BACKGROUND", (j, i), (j, i), colors.HexColor("#ffeaea"))
                )

    t.setStyle(TableStyle(table_style_cmds))
    story.append(t)

    # Signature block
    story.append(Spacer(1, 1 * cm))
    story.append(_build_signature_block())

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
