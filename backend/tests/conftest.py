from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES, QueryRegistry
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import audit as _audit  # noqa: F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: F401
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
