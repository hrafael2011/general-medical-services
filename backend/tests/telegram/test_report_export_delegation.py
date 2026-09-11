"""Exportaciones de médicos con filtros deben delegar al camino determinista.

Opción B de la bifurcación de reportes: extracción determinista con
`EntityResolver` en vez de enseñarle los reportes al NLU (que cambiaría el
prompt, zona estabilizada).
"""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.types import AgentResult


class _StubResolver:
    """EntityResolver de mentira: devuelve lo que se le indique, sin BD."""

    def __init__(self, resolved: dict | None = None, raises: bool = False) -> None:
        self._resolved = resolved or {}
        self._raises = raises
        self.calls = 0

    def pre_process(self, text: str) -> dict:
        self.calls += 1
        if self._raises:
            raise RuntimeError("resolver caído")
        return {"resolved": dict(self._resolved), "ambiguous": [], "hints": ""}


def _agent(resolver, doctor_service=None):
    agent = object.__new__(ConversationalAgent)
    agent._entity_resolver = resolver
    agent._doctor_query_service = doctor_service
    return agent


class TestDoctorExportResolved:
    def test_rank_export_is_recognized(self):
        agent = _agent(_StubResolver({"rank": {"normalized_name": "Sargento"}}))
        resolved = agent._doctor_export_resolved("Exporta en PDF los sargentos.")
        assert resolved is not None
        assert resolved["rank"]["normalized_name"] == "Sargento"

    def test_sex_export_is_recognized(self):
        agent = _agent(_StubResolver({"sex": "M"}))
        assert agent._doctor_export_resolved("Exporta en Excel los masculinos.") is not None

    def test_doctor_export_is_recognized(self):
        agent = _agent(_StubResolver({"doctor": {"id": "d1", "name": "ACOSTA"}}))
        assert agent._doctor_export_resolved("Exporta el perfil del doctor Acosta.") is not None

    def test_non_export_query_is_not_claimed(self):
        """Una consulta normal no debe desviarse al camino de reportes."""
        agent = _agent(_StubResolver({"rank": {"normalized_name": "Sargento"}}))
        assert agent._doctor_export_resolved("Cuantos sargentos hay?") is None

    def test_export_without_doctor_filter_is_not_claimed(self):
        """«Exporta el calendario de julio» no es una exportación de médicos."""
        agent = _agent(_StubResolver({}))
        assert agent._doctor_export_resolved("Exporta el calendario de julio en PDF.") is None

    def test_missing_resolver_abstains(self):
        agent = _agent(None)
        assert agent._doctor_export_resolved("Exporta en PDF los sargentos.") is None

    def test_resolver_failure_abstains_instead_of_crashing(self):
        agent = _agent(_StubResolver(raises=True))
        assert agent._doctor_export_resolved("Exporta en PDF los sargentos.") is None

    def test_resolver_not_called_for_non_export(self):
        """El resolver pega a la BD: no se le llama si la frase no es exportación."""
        resolver = _StubResolver({"rank": {"normalized_name": "Sargento"}})
        _agent(resolver)._doctor_export_resolved("Cuantos sargentos hay?")
        assert resolver.calls == 0


class _FakeBotClient:
    def __init__(self) -> None:
        self.messages = []
        self.documents = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))

    def send_document(self, chat_id, data, filename):
        self.documents.append((chat_id, filename))


class _FakeDoctorService:
    def __init__(self, result=None) -> None:
        self.calls = []
        self._result = result

    def execute(self, user_text, resolved):
        self.calls.append((user_text, resolved))
        if self._result is not None:
            return self._result
        return AgentResult(
            response_text="Aquí tienes el reporte solicitado. (1 registros, PDF).",
            agent_action="export",
            tool_name="doctor_query_service",
            document_bytes=b"%PDF-fake",
            document_filename="MEDICOS_FILTRADOS.pdf",
        )


def _orchestrator(agent, bot_client):
    from backend.app.application.telegram.orchestrator import TelegramOrchestrator

    orch = object.__new__(TelegramOrchestrator)
    orch._agent = agent
    orch._bot_client = bot_client
    orch._report_service = None
    return orch


def _report_decision(fmt="pdf"):
    from backend.app.application.telegram.message_router import TelegramRouteDecision

    return TelegramRouteDecision(
        route="report_request",
        confidence=0.9,
        reason="report_keyword_detected",
        normalized_text="exporta en pdf los sargentos.",
        requested_format=fmt,
        requires_llm=True,
    )


class TestOrchestratorDelegation:
    def test_doctor_export_delegates_and_sends_document(self):
        """«Exporta en PDF los sargentos» no nombra tipo de reporte: antes moría."""
        service = _FakeDoctorService()
        agent = _agent(_StubResolver({"rank": {"normalized_name": "Sargento"}}), service)
        bot = _FakeBotClient()
        orch = _orchestrator(agent, bot)

        result = orch._try_report_handler(
            text="Exporta en PDF los sargentos.",
            decision=_report_decision(),
            telegram_user_id="u1",
            chat_id=42,
            user=None,
        )

        assert service.calls, "el servicio determinista debe recibir la exportación"
        assert result is not None
        assert bot.documents == [(42, "MEDICOS_FILTRADOS.pdf")]

    def test_calendar_report_does_not_take_the_doctor_path(self):
        """La delegación no debe apropiarse de los reportes que no son de médicos."""
        service = _FakeDoctorService()
        agent = _agent(_StubResolver({}), service)
        orch = _orchestrator(agent, _FakeBotClient())

        orch._try_report_handler(
            text="Exporta el calendario de julio en PDF.",
            decision=_report_decision(),
            telegram_user_id="u1",
            chat_id=42,
            user=None,
        )

        assert service.calls == []

    def test_abstaining_service_falls_through_to_the_agent(self):
        """Si el servicio no produce nada, la frase sigue su curso normal.

        Devolver None es el contrato de este método: el orquestador cae al
        agente legacy, que responde o pide aclaración. Lo que no puede pasar es
        que la delegación se apropie de la frase y la deje muda.
        """
        service = _FakeDoctorService()
        service.execute = lambda user_text, resolved: None  # type: ignore[method-assign]
        agent = _agent(_StubResolver({"rank": {"normalized_name": "Sargento"}}), service)
        bot = _FakeBotClient()
        orch = _orchestrator(agent, bot)

        result = orch._try_report_handler(
            text="Exporta en PDF los sargentos.",
            decision=_report_decision(),
            telegram_user_id="u1",
            chat_id=42,
            user=None,
        )

        assert result is None, "debe caer al agente, no responder por su cuenta"
        assert bot.documents == [], "no debe enviar un documento que no se generó"
