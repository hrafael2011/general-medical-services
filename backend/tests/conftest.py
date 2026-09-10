"""Fixtures globales de la suite — todo corre contra PostgreSQL.

No queda ningún camino SQLite: la suite apunta al PostgreSQL de test
(`postgres-test`, puerto 5434) para que se pruebe contra el mismo motor que
producción. La base de desarrollo (5433) queda **fuera de alcance por
construcción** — ver el bloque de override más abajo.

Para cambiar el destino (CI, otro puerto): variable `TEST_DATABASE_URL`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Generator

# ═══════════════════════════════════════════════════════════════════════════
# Override de conexión — DEBE correr antes de importar la app.
#
# `backend.app.infrastructure.db.session` crea su engine al importarse, leyendo
# `settings.database_url`. Si este bloque corriera después de ese import, la
# app apuntaría a la base de DESARROLLO (5433) y la suite escribiría sobre
# datos reales. Por eso el override va primero y los imports llevan noqa E402.
# ═══════════════════════════════════════════════════════════════════════════

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from backend.app.application.telegram.registry import (  # noqa: E402
    DEFAULT_QUERY_TYPES,
    QueryRegistry,
)
from backend.app.core.config import settings  # noqa: E402
from backend.app.infrastructure.db.base import Base  # noqa: E402
from backend.app.infrastructure.db.models import action_alerts as _action_alerts  # noqa: E402, F401
from backend.app.infrastructure.db.models import audit as _audit  # noqa: E402, F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: E402, F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: E402, F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: E402, F401
from backend.app.infrastructure.db.models import confirmations as _confirmations  # noqa: E402, F401
from backend.app.infrastructure.db.models import doctors as _doctors  # noqa: E402, F401
from backend.app.infrastructure.db.models import missions as _missions  # noqa: E402, F401
from backend.app.infrastructure.db.models import notifications as _notifications  # noqa: E402, F401
from backend.app.infrastructure.db.models import set_password_token as _spt  # noqa: E402, F401
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: E402, F401
from backend.app.infrastructure.db.models import telegram_session as _ts  # noqa: E402, F401
from backend.app.infrastructure.db.models import user as _user  # noqa: E402, F401

settings.database_url = TEST_DATABASE_URL

# ── Blindaje de la limpieza entre tests ─────────────────────────────────────
# Una sesión que quede abierta retiene locks y bloquearía el TRUNCATE para
# siempre. Postgres la termina sola pasado el timeout de ociosidad.
_TEST_CONNECT_ARGS = {"options": "-c idle_in_transaction_session_timeout=10000"}
_TRUNCATE_LOCK_TIMEOUT = "12s"
_TRUNCATE_RETRIES = 3
_TRUNCATE_RETRY_WAIT = 3.0


# ═══════════════════════════════════════════════════════════════════════════
# Engine compartido — un solo schema para toda la corrida
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def pg_engine():
    """Engine contra el PostgreSQL de test, con el schema recreado por corrida."""
    engine = create_engine(
        TEST_DATABASE_URL, pool_pre_ping=True, connect_args=_TEST_CONNECT_ARGS
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _truncate_all(engine) -> None:
    """Vacía todas las tablas entre tests.

    Antes cada test recibía una base SQLite en memoria recién creada; ahora
    comparten schema, así que la limpieza es explícita. `TRUNCATE` de todas las
    tablas en una sola sentencia es rápido y `CASCADE` resuelve las FKs.

    Blindaje: `TRUNCATE` pide lock exclusivo, así que una sesión de test que
    quedara abierta lo bloquea indefinidamente (pasó — la suite se colgó 29
    minutos). El `lock_timeout` acota la espera y el
    `idle_in_transaction_session_timeout` del engine hace que Postgres termine
    la sesión ociosa; por eso se reintenta en vez de rendirse al primer intento.
    """
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if not tables:
        return
    for intento in range(1, _TRUNCATE_RETRIES + 1):
        try:
            with engine.begin() as conn:
                conn.execute(text(f"SET LOCAL lock_timeout = '{_TRUNCATE_LOCK_TIMEOUT}'"))
                conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
            return
        except SQLAlchemyError as exc:
            if intento == _TRUNCATE_RETRIES:
                # No enmascarar el fallo del test, pero que se vea fuerte: si la
                # limpieza no ocurre, los tests siguientes arrastran datos.
                print(
                    f"\n[conftest] AVISO: la limpieza de tablas falló {intento} veces "
                    f"({type(exc).__name__}). Una sesión de test quedó abierta "
                    f"reteniendo locks; los tests siguientes pueden ver datos sucios."
                )
                return
            time.sleep(_TRUNCATE_RETRY_WAIT)


def _session_factory(engine) -> sessionmaker:
    return sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )


@pytest.fixture
def engine(pg_engine):
    """Engine para tests que arman sus propias sesiones (rutas, seeds).

    Function-scoped a propósito: el teardown vacía las tablas, de modo que el
    test siguiente parte limpio aunque el anterior haya hecho commit.
    """
    yield pg_engine
    _truncate_all(pg_engine)


@pytest.fixture
def session_local(engine) -> sessionmaker:
    """Fábrica de sesiones contra el engine de test."""
    return _session_factory(engine)


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """Sesión contra PostgreSQL, con las tablas vaciadas al terminar el test."""
    session = _session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """Alias de `db_session` para los tests de rutas que inyectan la sesión."""
    session = _session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


# ═══════════════════════════════════════════════════════════════════════════
# Registry / router — SQL real de producción, sin adaptación
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def pg_registry() -> QueryRegistry:
    """QueryRegistry con los templates tal como corren en producción.

    Antes existía una variante adaptada a SQLite (`_adapt_to_sqlite`); ya no
    hay nada que adaptar: el motor de test es el de producción.
    """
    registry = QueryRegistry()
    for entry in DEFAULT_QUERY_TYPES:
        registry.register(
            query_type=entry["query_type"],
            sql_template=entry["sql_template"],
            params_schema=entry.get("params_schema", {}),
            description=entry.get("description", ""),
        )
    return registry


@pytest.fixture
def pg_router(pg_registry, seeded_db):
    """IntentRouter con los templates reales y la sesión sembrada."""
    from backend.app.application.telegram.intent_router import IntentRouter

    router = IntentRouter(registry=pg_registry)
    router.set_session(seeded_db["session"])
    return router


# ═══════════════════════════════════════════════════════════════════════════
# Guard — los tests marcados `db` / `e2e` saltan si el PostgreSQL no responde
# ═══════════════════════════════════════════════════════════════════════════


def _postgres_reachable() -> bool:
    if getattr(_postgres_reachable, "_cached", None) is not None:  # pragma: no cover
        return _postgres_reachable._cached
    engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 2})
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
