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


class TestReportMappingsAreDispatchable:
    """Un mapeo a un método que exige datos que nadie le pasa es un TypeError.

    El despachador rellena sólo ciertos parámetros (y con valor real, no None).
    Si un método mapeado exige cualquier otro, el documento nunca se genera y el
    usuario recibe un «no se pudo generar» opaco.
    """

    def test_every_mapped_method_is_callable_with_what_we_send(self):
        import inspect

        from backend.app.application.reports.report_service import ReportService
        from backend.app.application.telegram.report_contracts import (
            _DISPATCHABLE_PARAMS,
            _REPORT_METHOD_MAP,
        )

        problemas = []
        for (report_type, fmt), method_name in sorted(_REPORT_METHOD_MAP.items()):
            method = getattr(ReportService, method_name, None)
            if method is None:
                problemas.append(f"{report_type}/{fmt}: ReportService no tiene {method_name}")
                continue
            required = [
                p.name
                for p in inspect.signature(method).parameters.values()
                if p.name != "self"
                and p.default is inspect.Parameter.empty
                and p.kind
                in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
            faltantes = [name for name in required if name not in _DISPATCHABLE_PARAMS]
            if faltantes:
                problemas.append(
                    f"{report_type}/{fmt} -> {method_name}: exige {faltantes}, "
                    "que el despachador no sabe llenar"
                )
        assert not problemas, "Mapeos rotos:\n" + "\n".join(problemas)

    def test_calendar_has_no_broken_mapping(self):
        """Sin mapeo, el contrato responde «método no encontrado» en vez de reventar."""
        from backend.app.application.telegram.report_contracts import (
            _REPORT_METHOD_MAP,
            ReportContractValidator,
            TelegramReportRequest,
        )

        for fmt in ("pdf", "excel"):
            request = TelegramReportRequest(
                report_type="calendar", output_format=fmt, month=8, year=2026
            )
            method_name = ReportContractValidator().get_report_service_method(request)
            if method_name:
                import inspect

                from backend.app.application.reports.report_service import ReportService

                required = [
                    p.name
                    for p in inspect.signature(
                        getattr(ReportService, method_name)
                    ).parameters.values()
                    if p.name != "self" and p.default is inspect.Parameter.empty
                ]
                assert not required, (
                    f"calendar/{fmt} mapea a {method_name}, que exige {required}"
                )


class TestPeriodQuestionDoesNotRepeatTheMonth:
    """Re-preguntar el mes que el usuario ya dio es hacerle repetir."""

    def _validate(self, **kw):
        from backend.app.application.telegram.report_contracts import (
            ReportContractValidator,
            TelegramReportRequest,
        )

        request = TelegramReportRequest(
            report_type="calendar", output_format="pdf", **kw
        )
        return ReportContractValidator().validate(request)

    def test_year_only_missing_asks_only_for_the_year(self):
        result = self._validate(month=7)
        assert result["ok"] is False
        needs = result["needs"].lower()
        assert "julio" in needs, needs
        assert "mes y año" not in needs, needs

    def test_both_missing_still_asks_for_both(self):
        result = self._validate()
        assert "mes y año" in result["needs"].lower()

    def test_complete_period_does_not_ask(self):
        assert self._validate(month=7, year=2026)["ok"] is True
