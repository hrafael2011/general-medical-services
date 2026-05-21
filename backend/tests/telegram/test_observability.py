from datetime import UTC, datetime

from backend.app.application.telegram.doctor_query_service import DoctorQueryService
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.llm import FakeLLMProvider
from backend.app.infrastructure.db.models.doctors import DoctorModel


def test_router_query_returns_observability_metadata(db_session):
    router = IntentRouter()
    router.set_session(db_session)

    result = router.handle(
        action="query",
        query_type="count_doctors_total",
        params={},
        user_message="cuantos medicos tengo",
    )

    assert result.tool_name == "query_registry"
    assert result.tool_entities == {
        "query_type": "count_doctors_total",
        "params": {},
        "operation": "query",
    }
    assert result.tool_result["source"] == "query_registry"
    assert result.tool_result["query_type"] == "count_doctors_total"
    assert result.tool_result["row_count"] == 1


def test_doctor_query_service_returns_observability_metadata(db_session):
    now = datetime.now(UTC)
    db_session.add(
        DoctorModel(
            id="doctor-observability-female",
            name="Dra. Observabilidad",
            normalized_name="dra. observabilidad",
            sex="female",
            active=True,
            service_active=True,
            availability_mode="monthly",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()

    result = DoctorQueryService(db_session).execute(
        "cuantos medicos femeninos tengo",
        {"sex": "female"},
    )

    assert result is not None
    assert result.tool_result["source"] == "deterministic_doctor_query"
    assert result.tool_result["row_count"] == 1
    assert result.tool_entities["operation"] == "count"


def test_query_executor_exposes_top_level_row_count(db_session):
    executor = QueryExecutor(
        session=db_session,
        llm=FakeLLMProvider(responses={
            "cuantos": "SELECT COUNT(*) AS total FROM doctors",
        }),
    )

    result = executor.execute("cuantos medicos tengo")

    assert result["source"] == "nl_to_sql"
    assert result["row_count"] == 1
    assert result["data"]["row_count"] == 1
