"""Report contract layer — Pydantic validation before report generation.

Ensures the LLM cannot pass raw strings directly to WeasyPrint/openpyxl.
The contract validates report type, format, period, and filters before
any report service is called.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report type → required fields mapping
# ---------------------------------------------------------------------------

_REPORT_REQUIREMENTS: dict[str, list[str]] = {
    "calendar": ["month", "year"],
    "doctor_list": [],  # filters are optional
    "workload": ["month", "year"],
    "coverage": ["date_from", "date_to"],
    "mission_ranking": [],  # optional month/year
}

# Tier 1: Fully enabled — validated + generation wired to ReportService
_ENABLED_REPORT_TYPES: set[str] = {"calendar", "doctor_list", "workload"}

# Tier 2: Defined but disabled — contract validates, but generation is blocked
# until service verification is complete
_DEFINED_REPORT_TYPES: set[str] = {"coverage", "mission_ranking"}

# All recognized report types (union of enabled + defined)
_SUPPORTED_REPORT_TYPES: set[str] = _ENABLED_REPORT_TYPES | _DEFINED_REPORT_TYPES

# Human-readable report type names in Spanish
_REPORT_TYPE_LABELS: dict[str, str] = {
    "calendar": "calendario",
    "doctor_list": "listado de médicos",
    "workload": "carga de trabajo",
    "coverage": "cobertura",
    "mission_ranking": "ranking de misiones",
}


class TelegramReportRequest(BaseModel):
    """Validated contract for Telegram-initiated report generation.

    The LLM may help extract parameters into this contract, but the
    contract validates before any report service runs. No raw LLM
    string reaches WeasyPrint or openpyxl.
    """
    report_type: Literal[
        "calendar",
        "doctor_list",
        "workload",
        "coverage",
        "mission_ranking",
    ]
    output_format: Literal["pdf", "excel"]
    date_from: date | None = None
    date_to: date | None = None
    month: int | None = None
    year: int | None = None
    department: str | None = None
    service_area: str | None = None
    rank: str | None = None
    sex: Literal["male", "female"] | None = None

    @field_validator("month")
    @classmethod
    def month_must_be_valid(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 12):
            raise ValueError(f"Mes inválido: {v}. Debe ser 1-12.")
        return v

    @field_validator("year")
    @classmethod
    def year_must_be_reasonable(cls, v: int | None) -> int | None:
        if v is not None and (v < 2020 or v > 2100):
            raise ValueError(f"Año inválido: {v}.")
        return v


class ReportContractValidator:
    """Validates TelegramReportRequest against business rules."""

    def validate(self, request: TelegramReportRequest) -> dict[str, Any]:
        """Validate *request* and return a structured result.

        Returns:
            {"ok": bool, "needs": str|None, "enabled": bool}
            - ok=True, enabled=True: contract valid, proceed to generation
            - ok=True, enabled=False: contract valid but report type not yet enabled
            - ok=False: needs contains a clarification question in Spanish
        """
        # Check if report type is recognized
        if request.report_type not in _SUPPORTED_REPORT_TYPES:
            return {
                "ok": False,
                "needs": (
                    "No reconozco ese tipo de reporte. "
                    "Los reportes disponibles son: calendario, listado de médicos, "
                    "carga de trabajo, cobertura y ranking de misiones."
                ),
                "enabled": False,
            }

        # Check if report type is enabled for generation
        if request.report_type not in _ENABLED_REPORT_TYPES:
            label = _REPORT_TYPE_LABELS.get(request.report_type, request.report_type)
            return {
                "ok": False,
                "needs": (
                    f"El reporte de {label} aún no está habilitado para generación "
                    "automática. Estará disponible próximamente."
                ),
                "enabled": False,
            }

        requirements = _REPORT_REQUIREMENTS.get(request.report_type, [])

        # Check required period fields
        missing = []
        for field in requirements:
            if getattr(request, field, None) is None:
                missing.append(field)

        if missing:
            label = _REPORT_TYPE_LABELS.get(request.report_type, request.report_type)
            if "month" in missing or "year" in missing:
                return {
                    "ok": False,
                    "needs": (
                        f"¿Para qué mes y año necesitas el {label}? "
                        "Por favor indícame el periodo (ejemplo: julio 2026)."
                    ),
                    "enabled": True,
                }
            if "date_from" in missing or "date_to" in missing:
                return {
                    "ok": False,
                    "needs": (
                        f"¿Para qué rango de fechas necesitas el {label}? "
                        "Por favor indícame la fecha de inicio y fin."
                    ),
                    "enabled": True,
                }
            return {
                "ok": False,
                "needs": (
                    f"Necesito más información para generar el {label}. "
                    "¿Podrías ser más específico?"
                ),
                "enabled": True,
            }

        return {"ok": True, "needs": None, "enabled": True}

    def get_report_service_method(self, request: TelegramReportRequest) -> str:
        """Map a validated request to the corresponding ReportService method name."""
        mapping = {
            ("calendar", "excel"): "generate_calendar_excel",
            ("calendar", "pdf"): "generate_weekly_schedule_pdf",
            ("doctor_list", "excel"): "generate_doctor_history_excel",
            ("doctor_list", "pdf"): "generate_doctor_dossier",
            ("workload", "excel"): "generate_workload",
            ("workload", "pdf"): "generate_workload",
            ("coverage", "excel"): "generate_coverage",
            ("coverage", "pdf"): "generate_coverage",
            ("mission_ranking", "excel"): "generate_operational_summary",
            ("mission_ranking", "pdf"): "generate_operational_summary",
        }
        return mapping.get(
            (request.report_type, request.output_format), ""
        )
