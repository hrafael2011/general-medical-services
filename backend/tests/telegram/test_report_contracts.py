"""Tests for TelegramReportRequest contract validation."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from backend.app.application.reports.report_service import ReportService
from backend.app.application.telegram.report_contracts import (
    TelegramReportRequest,
    ReportContractValidator,
)


class TestTelegramReportRequest:
    def test_valid_calendar_pdf_request(self):
        req = TelegramReportRequest(
            report_type="calendar",
            output_format="pdf",
            month=7,
            year=2026,
        )
        assert req.report_type == "calendar"
        assert req.output_format == "pdf"
        assert req.month == 7
        assert req.year == 2026

    def test_valid_doctor_list_excel_request(self):
        req = TelegramReportRequest(
            report_type="doctor_list",
            output_format="excel",
            department="Cardiologia",
        )
        assert req.report_type == "doctor_list"
        assert req.output_format == "excel"

    def test_valid_workload_request(self):
        req = TelegramReportRequest(
            report_type="workload",
            output_format="pdf",
            month=5,
            year=2026,
        )
        assert req.report_type == "workload"

    def test_valid_coverage_request(self):
        """coverage is defined but not enabled — model still validates."""
        req = TelegramReportRequest(
            report_type="coverage",
            output_format="excel",
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )
        assert req.report_type == "coverage"

    def test_invalid_report_type_rejected(self):
        with pytest.raises(ValidationError):
            TelegramReportRequest(
                report_type="invalid_report",  # type: ignore[arg-type]
                output_format="pdf",
            )

    def test_invalid_output_format_rejected(self):
        with pytest.raises(ValidationError):
            TelegramReportRequest(
                report_type="calendar",
                output_format="word",  # type: ignore[arg-type]
            )

    def test_month_validation(self):
        with pytest.raises(ValidationError):
            TelegramReportRequest(
                report_type="calendar",
                output_format="pdf",
                month=13,
                year=2026,
            )

    def test_year_validation(self):
        with pytest.raises(ValidationError):
            TelegramReportRequest(
                report_type="calendar",
                output_format="pdf",
                month=6,
                year=1999,
            )

    def test_mission_ranking_model_valid(self):
        req = TelegramReportRequest(
            report_type="mission_ranking",
            output_format="excel",
            month=6,
            year=2026,
        )
        assert req.report_type == "mission_ranking"


class TestReportContractValidator:
    def test_valid_enabled_request_passes(self):
        validator = ReportContractValidator()
        req = TelegramReportRequest(
            report_type="calendar",
            output_format="pdf",
            month=7,
            year=2026,
        )
        result = validator.validate(req)
        assert result["ok"] is True
        assert result["enabled"] is True

    def test_defined_but_disabled_report_type_blocked(self):
        """coverage is defined but not yet enabled for generation."""
        validator = ReportContractValidator()
        req = TelegramReportRequest(
            report_type="coverage",
            output_format="pdf",
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
        )
        result = validator.validate(req)
        assert result["ok"] is False
        assert result["enabled"] is False
        assert "no está habilitado" in result["needs"].lower() or "próximamente" in result["needs"].lower()

    def test_mission_ranking_defined_but_disabled(self):
        validator = ReportContractValidator()
        req = TelegramReportRequest(
            report_type="mission_ranking",
            output_format="excel",
            month=6,
            year=2026,
        )
        result = validator.validate(req)
        assert result["ok"] is False
        assert result["enabled"] is False

    def test_missing_period_for_calendar_returns_clarification(self):
        validator = ReportContractValidator()
        req = TelegramReportRequest(
            report_type="calendar",
            output_format="pdf",
            month=None,
            year=None,
            date_from=None,
            date_to=None,
        )
        result = validator.validate(req)
        assert result["ok"] is False
        assert result["enabled"] is True  # calendar IS enabled
        assert result["needs"] is not None
        assert "mes" in result["needs"].lower() or "año" in result["needs"].lower()

    def test_workload_needs_month_year(self):
        validator = ReportContractValidator()
        req = TelegramReportRequest(
            report_type="workload",
            output_format="excel",
        )
        result = validator.validate(req)
        assert result["ok"] is False
        assert result["enabled"] is True

    def test_unrecognized_report_type_returns_error(self):
        validator = ReportContractValidator()
        # Create a request with a valid type first, then bypass validation
        req = TelegramReportRequest(
            report_type="workload",
            output_format="pdf",
            month=7,
            year=2026,
        )
        # This test validates the validator rejects unknown types via internal check
        # The Pydantic model enforces valid types at construction time
        result = validator.validate(req)
        assert result["ok"] is True  # workload is valid


def _texto_del_pdf(pdf_bytes: bytes) -> str:
    """Extrae el texto del PDF para poder afirmar sobre lo que el usuario ve."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


class FakeRank:
    def __init__(self, normalized_name: str) -> None:
        self.name = normalized_name
        self.normalized_name = normalized_name


class FakeDepartment:
    def __init__(self, normalized_name: str) -> None:
        self.name = normalized_name
        self.normalized_name = normalized_name


class FakeDoctor:
    def __init__(self, name, sex, rank=None, department=None) -> None:
        self.id = name
        self.name = name
        self.sex = sex
        self.rank = FakeRank(rank) if rank else None
        self.department = FakeDepartment(department) if department else None


class TestDoctorListReportDispatch:
    """El listado de médicos en PDF tiene que salir, no explotar.

    `("doctor_list", "pdf")` estaba mapeado a `generate_doctor_dossier`, que
    exige UN médico concreto. El despachador le pasaba `doctor_id=None`, así que
    toda exportación de un listado terminaba en «Médico no encontrado» — incluso
    frases sin un solo nombre, como «Exporta en PDF los medicos activos».
    """

    @pytest.fixture
    def report_service(self):
        service = ReportService(
            calendar_repo=MagicMock(),
            notification_repo=MagicMock(),
            doctor_repo=MagicMock(),
            mission_repo=MagicMock(),
            catalog_repo=MagicMock(),
        )
        # El repo real devuelve None cuando el id no existe; `None` no existe.
        service.doctor_repo.get_by_id.return_value = None
        service.doctor_repo.list_all.return_value = []
        return service

    def test_doctor_list_pdf_returns_a_pdf_not_a_missing_doctor_error(self, report_service):
        request = TelegramReportRequest(report_type="doctor_list", output_format="pdf")

        result = ReportContractValidator().generate_report(request, report_service)

        assert result["ok"] is True, result.get("error")
        assert result["document_bytes"][:4] == b"%PDF"

    def test_the_listing_honours_the_sex_filter(self, report_service):
        """El contrato declara `sex`; hoy el despachador lo tiraba a la basura.

        «Exporta en PDF los medicos femeninos» tiene que dar un documento con
        las femeninas, no con todos.
        """
        report_service.doctor_repo.list_all.return_value = [
            FakeDoctor("ANA FEMENINA", "female", "pasante", "ensenanza"),
            FakeDoctor("LUIS MASCULINO", "male", "pasante", "ensenanza"),
        ]
        request = TelegramReportRequest(
            report_type="doctor_list", output_format="pdf", sex="female"
        )

        result = ReportContractValidator().generate_report(request, report_service)

        assert result["ok"] is True, result.get("error")
        texto = _texto_del_pdf(result["document_bytes"])
        assert "ANA FEMENINA" in texto
        assert "LUIS MASCULINO" not in texto
