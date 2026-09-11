"""El detector de calendario es el embudo: si se abstiene, todo cae al SQL fallback."""
import pytest

from backend.app.application.telegram.operational_query_handler import (
    OperationalQueryHandler,
)


@pytest.fixture()
def handler():
    return OperationalQueryHandler(
        semantic_layer=None,
        doctor_service=None,
        calendar_service=None,
        intent_router=None,
        sql_executor=None,
    )


@pytest.mark.parametrize(
    "text,entities,expected",
    [
        ("¿Hay calendario de junio 2026?", {"month": 6, "year": 2026}, "calendar_status"),
        ("Cual es el estado del calendario de junio?", {"month": 6, "year": 2026}, "calendar_status"),
        ("El calendario de julio esta aprobado?", {"month": 7, "year": 2026}, "calendar_status"),
        ("Dame los calendarios pendientes de aprobacion.", {}, "calendar_status"),
        ("Dame los calendarios aprobados.", {}, "calendar_status"),
        ("Dame los huecos sin cubrir de julio.", {"month": 7, "year": 2026}, "calendar_status"),
        ("Hay cobertura completa en julio?", {"month": 7, "year": 2026}, "calendar_status"),
    ],
)
def test_status_queries_detected(handler, text, entities, expected):
    assert handler._detect_calendar_query(text, entities) == expected


def test_week_queries_detected(handler):
    assert (
        handler._detect_calendar_query(
            "Cuales son los medicos de servicio la primera semana de julio?",
            {"month": 7, "year": 2026},
        )
        == "calendar_assignments"
    )


def test_non_calendar_text_abstains(handler):
    assert handler._detect_calendar_query("Cuantos cabos hay?", {}) is None


class TestCalendarParamsDerivation:
    """`calendar_assignments` indexa params["start_date"] sin defensa.

    Devolver ese query_type sin fechas es el KeyError que dejaba al usuario sin
    respuesta. Por eso el detector y esta derivación son una sola unidad.
    """

    def test_week_query_derives_date_range(self, handler):
        params = handler._calendar_params_for(
            "calendar_assignments",
            {"month": 7, "year": 2026},
            "primera semana de julio",
        )
        assert params["start_date"] == "2026-07-01"
        assert params["end_date"] == "2026-07-07"

    def test_second_week_offsets_by_seven_days(self, handler):
        params = handler._calendar_params_for(
            "calendar_assignments",
            {"month": 7, "year": 2026},
            "segunda semana de julio",
        )
        assert params["start_date"] == "2026-07-08"
        assert params["end_date"] == "2026-07-14"

    def test_month_read_from_text_when_entities_lack_it(self, handler):
        params = handler._calendar_params_for(
            "calendar_assignments",
            {"year": 2026},
            "la tercera semana de agosto",
        )
        assert params["start_date"] == "2026-08-15"
        assert params["end_date"] == "2026-08-21"

    def test_fifth_week_does_not_overflow_short_month(self, handler):
        """Febrero no tiene día 29: anclar al último día real, no reventar."""
        params = handler._calendar_params_for(
            "calendar_assignments",
            {"month": 2, "year": 2026},
            "la quinta semana de febrero",
        )
        assert params["start_date"] == "2026-02-28"
        assert params["end_date"] == "2026-03-06"

    def test_no_month_means_no_range(self, handler):
        """Sin mes no hay rango: abstenerse en vez de reventar."""
        assert (
            handler._calendar_params_for(
                "calendar_assignments", {}, "la primera semana"
            )
            is None
        )

    def test_status_keeps_month_year(self, handler):
        params = handler._calendar_params_for(
            "calendar_status",
            {"month": 6, "year": 2026},
            "¿Hay calendario de junio 2026?",
        )
        assert params == {"month": 6, "year": 2026}

    def test_status_fills_month_from_text(self, handler):
        params = handler._calendar_params_for(
            "calendar_status", {}, "¿Hay calendario de julio 2026?"
        )
        assert params.get("month") == 7
        assert params.get("year") == 2026
