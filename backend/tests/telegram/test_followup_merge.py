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
