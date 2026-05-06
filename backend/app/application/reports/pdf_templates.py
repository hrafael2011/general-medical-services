"""
PDF templates for system reports using reportlab.

Generates professional PDFs with logo, headers, styled tables, and footers.
"""

import io
import os
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Image,
    PageBreak,
    PageTemplate,
    Frame,
    NextPageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_LOGO_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "static", "logo.png"
)


def _get_logo() -> Image | None:
    """Return logo Image if file exists, else None."""
    path = os.path.abspath(_LOGO_PATH)
    if os.path.isfile(path):
        try:
            img = Image(path, width=4 * cm, height=2 * cm)
            img.hAlign = "LEFT"
            return img
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

_styles = getSampleStyleSheet()

_TITLE = ParagraphStyle(
    "ReportTitle", parent=_styles["Title"], fontSize=18, spaceAfter=12, alignment=TA_CENTER
)

_SUBTITLE = ParagraphStyle(
    "ReportSubtitle",
    parent=_styles["Normal"],
    fontSize=11,
    spaceAfter=6,
    alignment=TA_CENTER,
    textColor=colors.grey,
)

_SECTION = ParagraphStyle(
    "SectionHeader",
    parent=_styles["Heading2"],
    fontSize=14,
    spaceBefore=16,
    spaceAfter=8,
    textColor=colors.HexColor("#1a56db"),
)

_CELL = ParagraphStyle(
    "CellStyle", parent=_styles["Normal"], fontSize=8, leading=10
)

_CELL_HEADER = ParagraphStyle(
    "CellHeader",
    parent=_styles["Normal"],
    fontSize=8,
    leading=10,
    textColor=colors.white,
    fontName="Helvetica-Bold",
)

_FOOTER = ParagraphStyle(
    "Footer", parent=_styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER
)


def _header_footer(canvas, doc):
    """Draw header line and page number on each page."""
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#1a56db"))
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(
        A4[0] / 2, 1 * cm, f"Pagina {doc.page}"
    )
    canvas.restoreState()


def _make_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """Build a styled table from a list of rows (first row = header)."""
    styled_rows: list[list[Paragraph]] = [
        [Paragraph(str(c), _CELL_HEADER) for c in data[0]],
    ]
    for row in data[1:]:
        styled_rows.append([Paragraph(str(c), _CELL) for c in row])

    t = Table(styled_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f9fafb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def _build_doc(title: str, subtitle: str) -> SimpleDocTemplate:
    """Create a base PDF document with header/footer template."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )
    return doc, buf


def _build_story(
    title: str,
    subtitle: str,
    sections: list[tuple[str, list[list[str]], list[float] | None]],
) -> list[object]:
    """Build PDF story with logo, title, subtitle, and sectioned tables."""
    story: list[object] = []

    logo = _get_logo()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(title, _TITLE))
    story.append(Paragraph(subtitle, _SUBTITLE))
    story.append(Spacer(1, 6 * mm))

    for section_title, table_data, col_widths in sections:
        story.append(Paragraph(section_title, _SECTION))
        if not table_data or len(table_data) < 2:
            story.append(Paragraph("Sin datos disponibles.", _CELL))
            story.append(Spacer(1, 4 * mm))
            continue
        story.append(_make_table(table_data, col_widths))
        story.append(Spacer(1, 6 * mm))

    return story


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------


def generate_calendar_pdf(
    assignments: list[dict],
    month: int,
    year: int,
) -> bytes:
    """Generate a PDF report of calendar assignments."""
    month_name = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ][month - 1]

    title = f"Calendario de Turnos - {month_name} {year}"
    subtitle = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    headers = ["Fecha", "Area", "Medico", "Fuente"]
    col_widths = [3.5 * cm, 4 * cm, 5.5 * cm, 3 * cm]
    rows = [headers]
    for a in assignments:
        rows.append([
            str(a.get("service_date", "")),
            str(a.get("service_area_name", a.get("service_area_id", ""))),
            str(a.get("doctor_name", a.get("doctor_id", ""))),
            str(a.get("assignment_source", "")),
        ])

    doc, buf = _build_doc(title, subtitle)
    story = _build_story(title, subtitle, [
        (f"Asignaciones ({len(assignments)} total)", rows, col_widths),
    ])
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def generate_doctor_history_pdf(
    doctor_data: list[dict],
    month: int,
    year: int,
) -> bytes:
    """Generate a PDF report of doctor service history."""
    month_name = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ][month - 1]

    title = f"Historial de Servicios - {month_name} {year}"
    subtitle = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    headers = ["Medico", "Servicios", "Areas", "Carga"]
    col_widths = [5 * cm, 2.5 * cm, 5.5 * cm, 2.5 * cm]
    rows = [headers]
    for d in doctor_data:
        rows.append([
            str(d.get("name", d.get("doctor_id", ""))),
            str(d.get("count", 0)),
            str(d.get("areas", "")),
            str(d.get("load", "")),
        ])

    doc, buf = _build_doc(title, subtitle)
    story = _build_story(title, subtitle, [
        (f"Resumen por Medico ({len(doctor_data)} medicos)", rows, col_widths),
    ])
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def generate_operational_summary_pdf(summary: dict) -> bytes:
    """Generate a PDF report of the operational summary."""
    period = summary.get("period", {})
    month = period.get("month", "?")
    year = period.get("year", "?")
    month_name = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    title = f"Resumen Operativo"
    subtitle = (
        f"{month_name[int(month) - 1] if isinstance(month, int) and 1 <= month <= 12 else month} {year} "
        f"| Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    # Key-value summary table
    rows = [
        ["Indicador", "Valor"],
        ["Medicos Activos", str(summary.get("active_doctors", 0))],
        [
            "Estado del Calendario",
            str(summary.get("calendar_status", "Sin calendario")),
        ],
        ["Asignaciones", str(summary.get("total_assignments", 0))],
        ["Huecos sin Resolver", str(summary.get("unresolved_gaps", 0))],
    ]

    doc, buf = _build_doc(title, subtitle)
    story: list[object] = []

    logo = _get_logo()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(title, _TITLE))
    story.append(Paragraph(subtitle, _SUBTITLE))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Indicadores del Periodo", _SECTION))
    story.append(_make_table(rows, col_widths=[5 * cm, 8 * cm]))
    story.append(Spacer(1, 6 * mm))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def generate_mission_ranking_pdf(
    entries: list[dict],
    month: int,
    year: int,
) -> bytes:
    """Generate a PDF report of mission candidate rankings."""
    month_name = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ][month - 1]

    title = f"Ranking de Candidatos - {month_name} {year}"
    subtitle = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    headers = ["#", "Medico", "Carga Total", "Elegible"]
    col_widths = [1.5 * cm, 6 * cm, 3 * cm, 2.5 * cm]
    rows = [headers]
    for e in entries:
        rows.append([
            str(e.get("position", "")),
            str(e.get("doctor_name", e.get("doctor_id", ""))),
            f"{float(e.get('total_load_score', 0)):.1f}",
            "Si" if e.get("eligible", False) else "No",
        ])

    doc, buf = _build_doc(title, subtitle)
    story = _build_story(title, subtitle, [
        (f"Ranking ({len(entries)} candidatos)", rows, col_widths),
    ])
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
