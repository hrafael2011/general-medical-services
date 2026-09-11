"""El merge de follow-up debe arrastrar período y responder a la anáfora.

`_merge_followup_context` sólo se llamaba en `_process_legacy`; el camino real
(`_process_llm_first`) no lo aplicaba, así que «No, en agosto» volvía a contar
julio.
"""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.memory import SessionState, SessionStore


class _FakeStore(SessionStore):
    def __init__(self, state):
        super().__init__()
        self._state = state

    def get(self, telegram_user_id):
        return self._state


def _agent(state):
    agent = object.__new__(ConversationalAgent)
    agent._session_store = _FakeStore(state) if state is not None else None
    return agent


class TestPeriodMerge:
    def test_month_correction_replaces_the_period(self):
        state = SessionState(
            last_filters={"rank": "sargento"},
            last_params={"month": 7, "year": 2026},
            last_period={"month": 7, "year": 2026},
            last_operation="count",
        )
        merged, _hints, applied, operation = _agent(state)._merge_followup_context(
            "u1", {}, "", "No, en agosto."
        )
        assert applied is True
        assert merged["month"] == 8
        assert merged["year"] == 2026
        assert merged.get("rank"), "el filtro anterior debe seguir"
        assert operation == "count"

    def test_without_a_month_the_previous_period_is_kept(self):
        state = SessionState(
            last_filters={"rank": "sargento"},
            last_period={"month": 7, "year": 2026},
            last_operation="count",
        )
        merged, _hints, applied, _op = _agent(state)._merge_followup_context(
            "u1", {}, "", "De esos, cuantos hay?"
        )
        assert applied is True
        assert merged["month"] == 7
        assert merged["year"] == 2026

    def test_explicit_month_wins_over_the_previous_period(self):
        state = SessionState(
            last_filters={"rank": "sargento"},
            last_period={"month": 7, "year": 2026},
            last_operation="count",
        )
        merged, _hints, _applied, _op = _agent(state)._merge_followup_context(
            "u1", {"month": 6}, "", "Y en junio?"
        )
        assert merged["month"] == 6


class TestPossessiveAnaphora:
    def test_su_rango_injects_the_last_subject(self):
        """«Dame su rango» debe referirse al médico del turno anterior."""
        state = SessionState(
            last_filters={},
            last_subject="ACOSTA RAMOS",
            last_operation="list",
        )
        merged, _hints, applied, _op = _agent(state)._merge_followup_context(
            "u1", {}, "", "Dame su rango."
        )
        assert applied is True
        assert merged.get("doctor_name") == "ACOSTA RAMOS"

    def test_no_subject_means_no_injection(self):
        state = SessionState(last_filters={"rank": "sargento"}, last_subject=None)
        merged, _hints, _applied, _op = _agent(state)._merge_followup_context(
            "u1", {}, "", "Dame su rango."
        )
        assert "doctor_name" not in merged


class _RecordingStore(SessionStore):
    def __init__(self):
        super().__init__()
        self.state = None

    def set(self, telegram_user_id, state):
        self.state = state


class TestRememberSubject:
    """Sin esto, «Dame su rango» no tiene a quién referirse."""

    def _remember(self, rows):
        from backend.app.application.telegram.types import AgentResult

        agent = object.__new__(ConversationalAgent)
        store = _RecordingStore()
        agent._session_store = store
        agent._remember_result(
            "u1",
            AgentResult(
                response_text="ok",
                agent_action="query",
                tool_name="doctor_query_service",
                tool_result={
                    "ok": True,
                    "data": {"columns": ["name", "sex", "rank"], "rows": rows},
                },
            ),
        )
        return store.state

    def test_single_doctor_result_becomes_the_subject(self):
        state = self._remember([{"name": "JOSE ACOSTA CABRERA", "sex": "male", "rank": "Cabo"}])
        assert state.last_subject == "JOSE ACOSTA CABRERA"

    def test_a_list_of_many_doctors_has_no_single_subject(self):
        state = self._remember([
            {"name": "JOSE ACOSTA CABRERA", "sex": "male", "rank": "Cabo"},
            {"name": "ANA MARTINEZ", "sex": "female", "rank": "Pasante"},
        ])
        assert state.last_subject is None

    def test_empty_result_has_no_subject(self):
        assert self._remember([]).last_subject is None


class TestGuards:
    def test_plain_question_is_not_a_followup(self):
        state = SessionState(last_filters={"rank": "sargento"}, last_subject="X")
        merged, _h, applied, _op = _agent(state)._merge_followup_context(
            "u1", {}, "", "Cuantos cabos hay?"
        )
        assert applied is False
        assert merged == {}

    def test_no_previous_filters_means_nothing_to_merge(self):
        state = SessionState(last_filters={}, last_subject="X")
        _h = None
        merged, _h, applied, _op = _agent(state)._merge_followup_context(
            "u1", {}, "", "Dame su rango."
        )
        # La anáfora sí puede resolverse aunque no haya filtros que arrastrar.
        assert applied is True
        assert merged.get("doctor_name") == "X"

    def test_existing_entities_are_not_overwritten(self):
        state = SessionState(
            last_filters={"rank": "sargento"},
            last_period={"month": 7, "year": 2026},
            last_operation="count",
        )
        merged, _h, _applied, _op = _agent(state)._merge_followup_context(
            "u1", {"rank": {"normalized_name": "Cabo"}}, "", "De esos, cuantos?"
        )
        assert merged["rank"]["normalized_name"] == "Cabo"


class _FakeNLU:
    def __init__(self, result):
        self._result = result

    def classify(self, text, conversation_history=None, system_context=None):
        return self._result


def _llm_first_agent(state, nlu_result, captured):
    from backend.app.application.telegram.agent import ConversationalAgent as Agent

    agent = object.__new__(Agent)
    agent._nlu_engine = _FakeNLU(nlu_result)
    agent._session_store = _FakeStore(state) if state is not None else None
    agent._session = None
    agent._input_sanitizer = type(
        "S", (), {"sanitize": staticmethod(lambda text: (True, text))}
    )()

    def _dispatch(tool_name, params, text, user=None):
        captured["tool"] = tool_name
        captured["params"] = dict(params)
        from backend.app.application.telegram.types import AgentResult

        return AgentResult(response_text="ok", agent_action="query", tool_name=tool_name)

    agent._dispatch_tool = _dispatch
    agent._generate_nl_response = lambda *a, **k: "ok"
    return agent


class TestLlmFirstAppliesTheMerge:
    """El camino real (`_process_llm_first`) no aplicaba el merge: sólo el legacy."""

    def _run(self, text, params, last_filters=None, last_period=None, last_subject=None):
        from backend.app.application.telegram.intent_classifier import NLUResult

        state = SessionState(
            last_filters=last_filters or {},
            last_period=last_period,
            last_subject=last_subject,
            last_operation="count",
        )
        captured: dict = {}
        agent = _llm_first_agent(
            state, NLUResult(tool="list_doctors", params=params, confidence=0.9), captured
        )
        agent._process_llm_first(text, "u1", history=[], start=0.0)
        return captured

    def test_period_correction_reaches_the_tool(self):
        captured = self._run(
            "No, en agosto.",
            {"count": True, "month": 8},
            last_filters={"rank": "sargento"},
            last_period={"month": 7, "year": 2026},
        )
        assert captured["params"]["month"] == 8
        assert captured["params"]["year"] == 2026

    def test_plain_query_is_left_alone(self):
        captured = self._run("Cuantos cabos hay?", {"count": True, "rank": "cabo"})
        assert captured["params"] == {"count": True, "rank": "cabo"}

    def test_possessive_anaphora_reaches_the_tool(self):
        captured = self._run(
            "Dame su rango.",
            {},
            last_filters={},
            last_subject="JOSE ACOSTA CABRERA",
        )
        assert captured["params"].get("doctor_name") == "JOSE ACOSTA CABRERA"

    def test_dict_valued_filters_are_not_stuffed_into_params(self):
        """`rank` llega como dict desde la memoria; los tools esperan un string."""
        captured = self._run(
            "De esos, cuantos hay?",
            {"count": True},
            last_filters={"rank": "sargento"},
            last_period={"month": 7, "year": 2026},
        )
        assert captured["params"]["month"] == 7
        assert not isinstance(captured["params"].get("rank"), dict)
