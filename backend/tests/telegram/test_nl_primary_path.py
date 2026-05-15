"""Tests for NL-to-SQL primary path and natural language response formatting."""
from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.types import AgentResult as AR


class FakeLLMForNL:
    """Fake LLM that returns action=query for router path, then scripted SQL for fallback."""

    def __init__(self, intent_json="", sql_response="", format_response=""):
        self.intent_json = intent_json or '{"action": "query", "query_type": "nonexistent"}'
        self.sql_response = sql_response
        self.format_response = format_response
        self.calls = []

    def chat_complete(self, messages, temperature=0.0, json_mode=False):
        self.calls.append({"temperature": temperature, "json_mode": json_mode})
        if temperature == 0.3:
            return self.format_response
        if json_mode or temperature == 0.0:
            return self.intent_json
        return self.sql_response


class FakeRouterNotFound:
    """Router that returns 'not found' to force fallback."""

    def __init__(self):
        self.registry = _FakeRegistry()

    def handle(self, **kwargs):
        return AR(response_text="No pude encontrar informacion sobre eso en el sistema.")


class FakeRouterEmpty:
    """Router that returns empty results."""

    def __init__(self):
        self.registry = _FakeRegistry()

    def handle(self, **kwargs):
        return AR(response_text="No se encontraron resultados para esa consulta.")


class _FakeRegistry:
    def get(self, name):
        return {
            "query_type": name,
            "sql_template": "",
            "params_schema": {},
            "description": "",
        }

    def list_all(self):
        return []


class FakeQueryExecutor:
    def __init__(self, rows=None, columns=None, ok=True):
        self.rows = rows or []
        self.columns = columns or []
        self.ok = ok
        self.last_entity_hints = None

    def execute(self, nl_query, user_text="", entity_hints=""):
        self.last_entity_hints = entity_hints
        if not self.ok:
            return {"ok": False, "error": "test error"}
        return {
            "ok": True,
            "data": {
                "columns": self.columns,
                "rows": self.rows,
                "row_count": len(self.rows),
                "truncated": False,
                "elapsed_seconds": 0.1,
            },
        }


def test_router_not_found_triggers_nl_fallback():
    """When router returns 'No pude encontrar', QueryExecutor fallback runs."""
    llm = FakeLLMForNL(
        intent_json='{"action": "query", "query_type": "nonexistent"}',
        format_response="Tienes 15 medicos masculinos en el sistema.",
    )
    qe = FakeQueryExecutor(rows=[{"total": 15}], columns=["total"])
    agent = ConversationalAgent(llm=llm, router=FakeRouterNotFound(), query_executor=qe)

    result = agent.process("cuantos medicos masculinos hay")
    assert result.agent_action == "query_db"
    assert "15" in result.response_text


def test_router_empty_results_triggers_nl_fallback():
    """When router returns empty results, QueryExecutor fallback is triggered."""
    llm = FakeLLMForNL(
        intent_json=(
            '{"action": "query", "query_type": "count_by_specific_rank", '
            '"params": {"rank": "cabo"}}'
        ),
        format_response="Tienes 8 cabos en el sistema.",
    )
    qe = FakeQueryExecutor(rows=[{"total": 8}], columns=["total"])
    agent = ConversationalAgent(llm=llm, router=FakeRouterEmpty(), query_executor=qe)

    result = agent.process("cuantos cabos hay")
    assert result.agent_action == "query_db"
    assert "8" in result.response_text


def test_entity_hints_passed_to_query_executor():
    """EntityResolver hints are forwarded to QueryExecutor for better SQL generation."""
    llm = FakeLLMForNL(
        intent_json='{"action": "query", "query_type": "nonexistent"}',
        sql_response="SELECT COUNT(*) AS total FROM doctors WHERE rank_id='r1'",
        format_response="Hay 8 cabos.",
    )
    qe = FakeQueryExecutor(rows=[{"total": 8}], columns=["total"])
    from backend.app.application.telegram.entity_resolver import EntityResolver

    resolver = EntityResolver(session=None)

    agent = ConversationalAgent(
        llm=llm,
        router=FakeRouterNotFound(),
        query_executor=qe,
        entity_resolver=resolver,
    )
    agent.process("cuantos cabos hay")
    # Entity hints should have been passed to QueryExecutor
    assert qe.last_entity_hints is not None


def test_nl_empty_response_when_no_data():
    """When QueryExecutor returns no rows, LLM formats a natural explanation."""
    llm = FakeLLMForNL(
        intent_json='{"action": "query", "query_type": "nonexistent"}',
        format_response="No encontre ningun medico con ese nombre en la base de datos.",
    )
    qe = FakeQueryExecutor(rows=[], columns=["id", "name"])
    agent = ConversationalAgent(llm=llm, router=FakeRouterNotFound(), query_executor=qe)

    result = agent.process("busca al doctor xyz")
    assert result.agent_action == "query_db"
    assert "No encontre" in result.response_text
