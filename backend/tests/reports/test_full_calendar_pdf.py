"""Tests for full calendar single-page PDF."""
from backend.app.application.reports.pdf_templates import generate_full_calendar_pdf


def test_generate_full_calendar_pdf_returns_bytes():
    """generate_full_calendar_pdf produces valid PDF bytes for a full month grid."""
    grid_data = {
        "month": 5,
        "year": 2026,
        "areas": ["EMERGENCIA", "PISTA", "DISPONIBLE", "ANALISIS INSTITUCIONAL", "BIENESTAR SOCIAL"],
        "rows": [
            {"day": 1, "day_name": "LUNES",
             "cells": {"EMERGENCIA": "CABO LOPEZ", "PISTA": "—", "DISPONIBLE": "—",
                       "ANALISIS INSTITUCIONAL": "—", "BIENESTAR SOCIAL": "—"}},
            {"day": 2, "day_name": "MARTES",
             "cells": {"EMERGENCIA": "—", "PISTA": "CABO CRUZ", "DISPONIBLE": "—",
                       "ANALISIS INSTITUCIONAL": "SGTO. BALBUENA", "BIENESTAR SOCIAL": "—"}},
        ],
        "summary": {"total_services": 45, "gaps": 12, "active_doctors": 21, "coverage_pct": 79},
    }
    result = generate_full_calendar_pdf(grid_data)
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"%PDF"


def test_generate_full_calendar_pdf_handles_empty():
    """Empty grid produces valid PDF bytes without crashing."""
    grid_data = {
        "month": 6, "year": 2026, "areas": [],
        "rows": [],
        "summary": {"total_services": 0, "gaps": 0, "active_doctors": 0, "coverage_pct": 0},
    }
    result = generate_full_calendar_pdf(grid_data)
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert result[:4] == b"%PDF"
