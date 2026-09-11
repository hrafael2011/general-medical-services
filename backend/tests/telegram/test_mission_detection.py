"""Detección determinista de consultas de misión — antes del fallback SQL.

El fallo dominante de este cluster eran 13 turnos que respondían «Se encontraron
41 resultados» (la lista de médicos) a preguntas sobre misiones: el NLU los
clasificaba como dominio «medicos» y el servicio de médicos los absorbía.
"""
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
    "text,expected",
    [
        ("Dame las misiones de julio.", "list_active_missions"),
        ("Dame las misiones de agosto.", "list_active_missions"),
        ("Hay misiones creadas en julio?", "list_active_missions"),
        ("Dame las misiones pendientes de reemplazo.", "pending_mission_confirmation"),
        ("Dame el ranking de misiones de julio.", "mission_ranking"),
        ("Dame candidatos ordenados de menor carga a mayor carga.", "mission_ranking"),
        ("Dame resumen de misiones por mes.", "operational_summary"),
    ],
)
def test_mission_phrases_detected(handler, text, expected):
    assert handler._detect_router_query(text, {}) == expected


def test_non_mission_text_abstains(handler):
    assert handler._detect_router_query("Cuantos cabos hay?", {}) is None


class _FakeRouter:
    def __init__(self, response="MISIONES: 3 activas"):
        self.calls = []
        self._response = response

    def handle(self, *, action, query_type, params):
        self.calls.append((action, query_type))
        if self._response is None:
            return None
        from backend.app.application.telegram.types import AgentResult

        return AgentResult(
            response_text=self._response, agent_action="query", tool_name="intent_router"
        )


class _FakeDoctorService:
    def __init__(self):
        self.calls = []

    def execute(self, user_text, resolved):
        self.calls.append(user_text)
        from backend.app.application.telegram.types import AgentResult

        return AgentResult(
            response_text="Se encontraron 41 resultados.", agent_action="query"
        )


def _handler_with(router, doctor_service):
    return OperationalQueryHandler(
        semantic_layer=None,
        doctor_service=doctor_service,
        calendar_service=None,
        intent_router=router,
        sql_executor=None,
    )


class TestMissionGate:
    def test_mission_phrase_never_reaches_the_doctor_service(self):
        """«Dame las misiones de agosto» respondía con 41 médicos."""
        doctors = _FakeDoctorService()
        handler = _handler_with(_FakeRouter(), doctors)

        result = handler.resolve(
            user_text="Dame las misiones de agosto.",
            domain="medicos",  # el NLU las clasifica así hoy
            action="query",
            entities={},
        )

        assert doctors.calls == [], "el servicio de médicos no debe absorber misiones"
        assert result is not None
        assert "MISIONES" in result.response_text

    def test_doctor_query_still_works(self):
        """La contracara: una consulta de médicos de verdad sigue su camino."""
        doctors = _FakeDoctorService()
        handler = _handler_with(_FakeRouter(), doctors)

        result = handler.resolve(
            user_text="Cuantos cabos hay?",
            domain="medicos",
            action="query",
            entities={},
        )

        assert doctors.calls == ["Cuantos cabos hay?"]
        assert result is not None
        assert "41" in result.response_text

    def test_router_without_answer_still_not_the_doctor_list(self):
        """Aunque el router no sepa responder, la lista de médicos no es opción."""
        doctors = _FakeDoctorService()
        handler = _handler_with(_FakeRouter(response=None), doctors)

        handler.resolve(
            user_text="Dame las misiones de agosto.",
            domain="medicos",
            action="query",
            entities={},
        )

        assert doctors.calls == []
