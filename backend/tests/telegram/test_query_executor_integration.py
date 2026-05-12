"""
Tests de integración para QueryExecutor con DeepSeekProvider real.

Requieren DEEPSEEK_API_KEY en .env. Se saltean automáticamente si no está configurada.
Usan el DB SQLite en memoria del fixture db_session — el LLM genera SQL,
pero puede producir sintaxis PostgreSQL que SQLite no soporta. Las pruebas
verifican la estructura de respuesta más que el contenido exacto.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.app.application.telegram.llm import DeepSeekProvider, FakeLLMProvider
from backend.app.application.telegram.query_executor import QueryExecutor, _build_schema_summary
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.doctors import DoctorModel

requires_deepseek = pytest.mark.skipif(
    not settings.deepseek_api_key,
    reason="DEEPSEEK_API_KEY no configurada",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_doctors(db_session, count: int = 3) -> list[DoctorModel]:
    doctors = []
    for i in range(count):
        now = datetime.now(UTC)
        d = DoctorModel(
            id=str(uuid.uuid4()),
            name=f"Dr. Prueba {i}",
            normalized_name=f"dr. prueba {i}",
            sex="M",
            service_active=True,
            availability_mode="weekly",
            monthly_service_target=4,
            monthly_service_max=6,
            created_at=now,
            updated_at=now,
        )
        db_session.add(d)
        doctors.append(d)
    db_session.flush()
    return doctors


# ---------------------------------------------------------------------------
# Schema summary (no LLM needed)
# ---------------------------------------------------------------------------

def test_build_schema_summary_without_session() -> None:
    summary = _build_schema_summary(session=None)
    assert "TABLE doctors" in summary
    assert "TABLE calendars" in summary
    assert "TABLE service_areas" in summary


def test_build_schema_summary_with_session(db_session) -> None:
    summary = _build_schema_summary(session=db_session)
    assert "TABLE doctors" in summary
    assert "VALORES REALES" in summary


def test_excluded_tables_not_in_schema() -> None:
    summary = _build_schema_summary(session=None)
    assert "TABLE audit_logs" not in summary
    assert "TABLE telegram_interactions" not in summary
    assert "TABLE alembic_version" not in summary


# ---------------------------------------------------------------------------
# SQL validation (no LLM, no DB)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def executor_no_db() -> QueryExecutor:
    """QueryExecutor con sesión None — solo para probar validación y extracción."""
    fake_session = MagicMock()
    fake_session.execute.side_effect = Exception("no DB")
    return QueryExecutor(session=fake_session, llm=FakeLLMProvider())


def test_validate_select_allowed(executor_no_db: QueryExecutor) -> None:
    assert executor_no_db._validate_sql("SELECT * FROM doctors") is True


def test_validate_insert_blocked(executor_no_db: QueryExecutor) -> None:
    assert executor_no_db._validate_sql("INSERT INTO doctors VALUES (1)") is False


def test_validate_delete_blocked(executor_no_db: QueryExecutor) -> None:
    assert executor_no_db._validate_sql("DELETE FROM doctors") is False


def test_validate_drop_blocked(executor_no_db: QueryExecutor) -> None:
    assert executor_no_db._validate_sql("DROP TABLE doctors") is False


def test_validate_cte_dml_blocked(executor_no_db: QueryExecutor) -> None:
    sql = "WITH x AS (SELECT 1) DELETE FROM doctors"
    assert executor_no_db._validate_sql(sql) is False


def test_extract_sql_from_markdown_block(executor_no_db: QueryExecutor) -> None:
    raw = "```sql\nSELECT * FROM doctors\n```"
    assert executor_no_db._extract_sql(raw) == "SELECT * FROM doctors"


def test_extract_sql_plain(executor_no_db: QueryExecutor) -> None:
    raw = "SELECT id FROM doctors WHERE service_active = 1"
    assert executor_no_db._extract_sql(raw) == raw


# ---------------------------------------------------------------------------
# Full execute() con LLM real + SQLite
# ---------------------------------------------------------------------------

@pytest.fixture
def real_executor(db_session) -> QueryExecutor:
    return QueryExecutor(session=db_session, llm=DeepSeekProvider())


@pytest.mark.integration
@requires_deepseek
def test_execute_returns_ok_structure(real_executor: QueryExecutor, db_session) -> None:
    _seed_doctors(db_session)
    result = real_executor.execute("¿Cuántos médicos hay en el sistema?")
    # El LLM puede generar SQL incompatible con SQLite — verificamos la estructura
    assert "ok" in result
    if result["ok"]:
        assert "data" in result
        assert "columns" in result["data"]
        assert "rows" in result["data"]
        assert "row_count" in result["data"]


@pytest.mark.integration
@requires_deepseek
def test_execute_select_only_query(real_executor: QueryExecutor, db_session) -> None:
    _seed_doctors(db_session, count=5)
    result = real_executor.execute("Lista los nombres de todos los médicos activos")
    assert "ok" in result


@pytest.mark.integration
@requires_deepseek
def test_execute_empty_db_returns_ok_or_error(real_executor: QueryExecutor) -> None:
    result = real_executor.execute("¿Cuántos calendarios hay?")
    assert "ok" in result


@pytest.mark.integration
@requires_deepseek
def test_execute_nonsense_query_does_not_raise(real_executor: QueryExecutor) -> None:
    result = real_executor.execute("xyzxyzxyz datos aleatorios sin sentido")
    assert "ok" in result


@pytest.mark.integration
@requires_deepseek
def test_generate_sql_returns_string(real_executor: QueryExecutor) -> None:
    sql = real_executor._generate_sql("¿Cuántos médicos activos hay?")
    assert isinstance(sql, str)
    assert len(sql.strip()) > 0


@pytest.mark.integration
@requires_deepseek
def test_generate_sql_starts_with_select(real_executor: QueryExecutor) -> None:
    sql = real_executor._generate_sql("Lista todos los médicos")
    extracted = real_executor._extract_sql(sql)
    assert extracted.strip().upper().startswith("SELECT")


@pytest.mark.integration
@requires_deepseek
def test_schema_summary_cached_on_init(real_executor: QueryExecutor) -> None:
    summary = real_executor.get_schema_summary()
    assert isinstance(summary, str)
    assert "TABLE doctors" in summary
