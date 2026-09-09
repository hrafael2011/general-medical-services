from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES, QueryRegistry
from backend.app.core.config import settings
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import action_alerts as _action_alerts  # noqa: F401
from backend.app.infrastructure.db.models import audit as _audit  # noqa: F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: F401
from backend.app.infrastructure.db.models import confirmations as _confirmations  # noqa: F401
from backend.app.infrastructure.db.models import doctors as _doctors  # noqa: F401
from backend.app.infrastructure.db.models import missions as _missions  # noqa: F401
from backend.app.infrastructure.db.models import notifications as _notifications  # noqa: F401
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: F401
from backend.app.infrastructure.db.models import user as _user  # noqa: F401


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    with SessionLocal() as session:
        yield session


# ═══════════════════════════════════════════════════════════════════════════
# SQLite adaptation helpers — PostgreSQL → SQLite for test templates
# ═══════════════════════════════════════════════════════════════════════════

_PG_TO_SQLITE_REPLACEMENTS = {
    "TRUE": "1",
    "FALSE": "0",
    "ILIKE": "LIKE",
    "CURRENT_DATE - INTERVAL '60 days'": "date('now', '-60 days')",
}


def _adapt_to_sqlite(sql: str) -> str:
    """Adapt PostgreSQL SQL template to SQLite-compatible syntax."""
    result = sql
    for pg, sq in _PG_TO_SQLITE_REPLACEMENTS.items():
        result = result.replace(pg, sq)
    return result


@pytest.fixture
def sqlite_registry() -> QueryRegistry:
    """QueryRegistry with DEFAULT_QUERY_TYPES adapted for SQLite."""
    registry = QueryRegistry()
    for entry in DEFAULT_QUERY_TYPES:
        registry.register(
            query_type=entry["query_type"],
            sql_template=_adapt_to_sqlite(entry["sql_template"]),
            params_schema=entry.get("params_schema", {}),
            description=entry.get("description", ""),
        )
    return registry


@pytest.fixture
def sqlite_router(sqlite_registry, seeded_db):
    """IntentRouter with SQLite-adapted templates and seeded session."""
    from backend.app.application.telegram.intent_router import IntentRouter

    router = IntentRouter(registry=sqlite_registry)
    router.set_session(seeded_db["session"])
    return router


# ═══════════════════════════════════════════════════════════════════════════
# PostgreSQL guard — tests marcados @pytest.mark.db saltan si no hay servidor
# ═══════════════════════════════════════════════════════════════════════════


def _postgres_reachable() -> bool:
    if getattr(_postgres_reachable, "_cached", None) is not None:  # pragma: no cover
        return _postgres_reachable._cached
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 2})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        _postgres_reachable._cached = False
        return False
    finally:
        engine.dispose()
    _postgres_reachable._cached = True
    return True


@pytest.fixture(scope="session")
def postgres_available() -> bool:
    return _postgres_reachable()


@pytest.fixture(autouse=True)
def _skip_db_tests_without_postgres(request) -> None:
    """Autouse: si el test está marcado `db` (o `e2e`) y no hay PG, saltar limpio."""
    if not _is_db_or_e2e(request.node):
        return
    if not _postgres_reachable():
        pytest.skip("PostgreSQL no disponible (marcador db/e2e)")


def pytest_collection_modifyitems(config, items) -> None:
    """Salta en colección los tests `db`/`e2e` sin PG — antes de que sus fixtures de
    scope superior (p.ej. module-scoped) intenten conectar y produzcan ERROR."""
    marked = [item for item in items if _is_db_or_e2e(item)]
    if not marked or _postgres_reachable():
        return
    skip_marker = pytest.mark.skip(reason="PostgreSQL no disponible (marcador db/e2e)")
    for item in marked:
        item.add_marker(skip_marker)


def _is_db_or_e2e(item) -> bool:
    return bool(item.get_closest_marker("db") or item.get_closest_marker("e2e"))
