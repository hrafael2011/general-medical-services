"""Alcance declarado del bot: qué contesta y qué rechaza.

El bug dominante del corpus no era que el NLU entendiera mal — entendía bien
(`reply/out_of_scope` para «Que hora es?»). Era que el enrutado IGNORABA esa
clasificación y volcaba la lista completa de médicos: 52 turnos del corpus
respondían «Se encontraron 41 resultados» a preguntas que no eran sobre
médicos.

Este módulo corta esa cadena en un solo lugar, con la lista de lo que los
servicios determinísticos SÍ saben responder.
"""
import pytest

from backend.app.application.telegram.scope_gate import (
    SCOPE_REFUSAL,
    SUPPORTED_TOOLS,
    check_scope,
)


class TestToolFueraDeAlcance:
    @pytest.mark.parametrize(
        "tool",
        [
            "audit_history",       # 3 volcados, 0 aciertos
            "action_alerts",       # 2 volcados, 0 aciertos
            "notification_status", # 1 volcado, 0 aciertos
            "doctor_restrictions", # 1 volcado, 0 aciertos
            "workload_ranking",    # 6 volcados, 0 aciertos en este paso
            "confirmation_status", # 2 volcados, 0 aciertos en este paso
            "slot_recommendation",
            "system_config",
        ],
    )
    def test_tool_no_soportado_se_rechaza(self, tool):
        assert check_scope(tool, {}) == "tool_fuera_de_alcance"

    def test_tool_soportado_pasa(self):
        assert check_scope("calendar_status", {"month": 8, "year": 2026}) is None

    def test_sin_clasificacion_no_se_juzga(self):
        """Sin tool del NLU no hay nada que comparar: no se rechaza a ciegas."""
        assert check_scope(None, {}) is None


class TestFiltrosQueNadieAplica:
    """El NLU completa parámetros que `DoctorQueryService` descarta en silencio.

    Con `group_by` o `service_active` el servicio no filtra nada y devuelve
    TODOS los médicos: el usuario pide «un resumen por rango» y recibe 41
    nombres. Es peor que un rechazo, porque parece una respuesta.
    """

    @pytest.mark.parametrize(
        "params",
        [
            {"group_by": "sex"},
            {"group_by": "rank"},
            {"service_active": True},
            {"pool_active": False},
            {"service_area": "Emergencia"},
            {"no_assignments_in": {"month": 7, "year": 2026}},
            {"participa_misiones": True},
        ],
    )
    def test_filtro_no_soportado_se_rechaza(self, params):
        assert check_scope("list_doctors", params) == "filtro_no_soportado"

    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"sex": "F"},
            {"rank": "Cabo"},
            {"sex": "F", "rank": "Cabo"},
            {"doctor_name": "Acosta"},
            {"count": True},
            {"user_text": "Dame los medicos."},
        ],
    )
    def test_filtros_soportados_pasan(self, params):
        assert check_scope("list_doctors", params) is None

    def test_un_filtro_malo_entre_buenos_igual_rechaza(self):
        """Basta un parámetro que nadie aplica para que la respuesta mienta."""
        assert check_scope(
            "list_doctors", {"sex": "F", "group_by": "rank"}
        ) == "filtro_no_soportado"


class TestConversacional:
    def test_reply_no_se_rechaza_aca(self):
        """`reply` lo contesta el agente con su respuesta conversacional.

        Rechazarlo acá borraría «Cuantos hay?» → 40, que se resuelve en la
        capa semántica antes de llegar a este punto.
        """
        assert check_scope("reply", {"response_type": "out_of_scope"}) is None

    def test_reply_no_esta_entre_las_capacidades_de_datos(self):
        assert "reply" not in SUPPORTED_TOOLS


def test_la_frase_de_rechazo_no_promete_datos():
    """El rechazo no puede sonar a que después va a contestar."""
    assert "no forma parte" in SCOPE_REFUSAL.lower()
    assert SCOPE_REFUSAL.strip().endswith(".")


class _DummyDoctorResult:
    def __init__(self, response_text="Se encontraron 41 resultados. Los primeros: ..."):
        self.ok = True
        self.response_text = response_text
        self.match_type = "doctor_service"
        self.used_sql = False
        self.fallback_reason = None


class _Handler:
    """`resolve()` con el servicio de médicos espiado."""

    @staticmethod
    def build(doctor_service):
        from backend.app.application.telegram.operational_query_handler import (
            OperationalQueryHandler,
        )

        return OperationalQueryHandler(
            semantic_layer=None,
            doctor_service=doctor_service,
            calendar_service=None,
            intent_router=None,
            sql_executor=None,
            llm_provider=None,
        )


class TestResolveRechazaFueraDeAlcance:
    def test_tool_no_soportado_no_llega_al_servicio_de_medicos(self):
        """«Dame auditoria de cambios del calendario» no puede volcar 41 médicos."""
        from unittest.mock import MagicMock

        doctor_service = MagicMock()
        doctor_service.execute.return_value = _DummyDoctorResult()
        handler = _Handler.build(doctor_service)

        result = handler.resolve(
            user_text="Dame auditoria de cambios del calendario de julio.",
            domain="medicos",
            action="query",
            entities={},
            nlu_tool="audit_history",
        )

        doctor_service.execute.assert_not_called()
        assert result is not None
        assert result.response_text == SCOPE_REFUSAL
        assert result.match_type == "scope_refusal"
        # ok=True para que el orquestador devuelva el rechazo en vez de
        # seguir bajando al agente, que volvería a volcar los médicos.
        assert result.ok is True

    def test_filtro_no_soportado_tampoco_llega(self):
        from unittest.mock import MagicMock

        doctor_service = MagicMock()
        doctor_service.execute.return_value = _DummyDoctorResult()
        handler = _Handler.build(doctor_service)

        result = handler.resolve(
            user_text="Dame un resumen por rango.",
            domain="medicos",
            action="list",
            entities={"group_by": "rank", "user_text": "Dame un resumen por rango."},
            nlu_tool="list_doctors",
        )

        doctor_service.execute.assert_not_called()
        assert result is not None
        assert result.response_text == SCOPE_REFUSAL

    def test_consulta_en_alcance_sigue_respondiendo(self):
        from unittest.mock import MagicMock

        doctor_service = MagicMock()
        doctor_service.execute.return_value = _DummyDoctorResult(
            "Se encontraron 11 resultados. Los primeros: ..."
        )
        handler = _Handler.build(doctor_service)

        result = handler.resolve(
            user_text="Dame la lista de cabos.",
            domain="medicos",
            action="list",
            entities={"rank": "Cabo"},
            nlu_tool="list_doctors",
        )

        doctor_service.execute.assert_called_once()
        assert result is not None
        assert "11" in result.response_text

    def test_reply_se_delega_al_agente(self):
        """`reply` no se rechaza acá: el agente tiene la respuesta conversacional."""
        from unittest.mock import MagicMock

        doctor_service = MagicMock()
        handler = _Handler.build(doctor_service)

        result = handler.resolve(
            user_text="Que me recomiendas?",
            domain="medicos",
            action="query",
            entities={},
            nlu_tool="reply",
        )

        doctor_service.execute.assert_not_called()
        assert result is None

    def test_sin_tool_el_comportamiento_no_cambia(self):
        """El camino sin NLU no se juzga: no se puede rechazar lo que no se clasificó."""
        from unittest.mock import MagicMock

        doctor_service = MagicMock()
        doctor_service.execute.return_value = _DummyDoctorResult()
        handler = _Handler.build(doctor_service)

        result = handler.resolve(
            user_text="Cuantos medicos hay",
            domain="medicos",
            action="count",
            entities={},
        )

        doctor_service.execute.assert_called_once()
        assert result is not None


class TestAgenteRechazaFueraDeAlcance:
    """Segunda capa: lo que llega al agente tampoco puede volcar los médicos.

    El orquestador no siempre intercepta —si devuelve None, la frase sigue
    hasta el agente—, y el `_dispatch_tool` del agente termina en el agente SQL
    como último recurso, que es otra forma de contestar cualquier cosa.
    """

    @staticmethod
    def _agent(*, tool, params):
        from unittest.mock import MagicMock

        from backend.app.application.telegram.agent import ConversationalAgent
        from backend.app.application.telegram.intent_classifier import NLUResult

        agent = object.__new__(ConversationalAgent)
        agent._input_sanitizer = MagicMock()
        agent._input_sanitizer.sanitize.return_value = (True, "")
        agent._nlu_engine = MagicMock()
        agent._nlu_engine.classify.return_value = NLUResult(tool=tool, params=params)
        agent._session = None
        agent._memory = None
        agent._session_store = None
        agent._dispatch_tool = MagicMock(return_value={"rows": []})
        agent._generate_nl_response = MagicMock(return_value="respuesta del LLM")
        agent._remember_result = MagicMock()
        return agent

    def test_tool_fuera_de_alcance_no_se_despacha(self):
        agent = self._agent(tool="audit_history", params={})

        result = agent._process_llm_first("Quien aprobo el calendario?", "u1", [], 0.0)

        agent._dispatch_tool.assert_not_called()
        assert result.response_text == SCOPE_REFUSAL
        assert result.agent_action == "unsupported"

    def test_filtro_no_soportado_no_se_despacha(self):
        agent = self._agent(tool="list_doctors", params={"group_by": "rank"})

        result = agent._process_llm_first("Dame un resumen por rango.", "u1", [], 0.0)

        agent._dispatch_tool.assert_not_called()
        assert result.response_text == SCOPE_REFUSAL

    def test_consulta_en_alcance_si_se_despacha(self):
        agent = self._agent(tool="list_doctors", params={"rank": "Cabo"})

        result = agent._process_llm_first("Dame la lista de cabos.", "u1", [], 0.0)

        agent._dispatch_tool.assert_called_once()
        assert result.response_text == "respuesta del LLM"

    def test_reply_sigue_yendo_a_la_respuesta_conversacional(self):
        """Un saludo no puede convertirse en un rechazo."""
        from unittest.mock import MagicMock

        from backend.app.application.telegram.types import AgentResult

        agent = self._agent(tool="reply", params={"response_type": "greeting"})
        agent._handle_reply = MagicMock(
            return_value=AgentResult(response_text="¡Hola!", agent_action="reply")
        )

        result = agent._process_llm_first("Hola", "u1", [], 0.0)

        agent._handle_reply.assert_called_once()
        agent._dispatch_tool.assert_not_called()
        assert result.response_text == "¡Hola!"
