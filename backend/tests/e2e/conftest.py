"""Fixtures E2E — FastAPI TestClient contra PostgreSQL descartable (puerto 5434).

Cada corrida hace drop_all + create_all del schema y re-siembra con
`backend.scripts.seed_e2e`, de modo que la suite es autocontenida y NUNCA
toca la base de desarrollo (5433). El runner (`scripts/test.sh e2e`) corre
migraciones + seed antes de pytest; este reset por corrida garantiza que los
tests partan de un estado conocido aunque algo haya quedado de corridas previas.

El guard del conftest global se sobrescribe aquí para comprobar postgres-test
(5434) en lugar de la base de desarrollo.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

# Importar TODOS los modelos para que Base.metadata los conozca
# (mismo set que el conftest global + set_password_token y telegram_session).
from backend.app.infrastructure.db import models as _models_pkg  # noqa: F401
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
from backend.app.infrastructure.db.models import (
    set_password_token as _set_password_token,  # noqa: F401
)
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: F401
from backend.app.infrastructure.db.models import telegram_session as _telegram_session  # noqa: F401
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.scripts.seed_e2e import seed

E2E_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test"
)


# ═══════════════════════════════════════════════════════════════════════════
# Guard — salta si postgres-test (5434) no responde
# ═══════════════════════════════════════════════════════════════════════════


def _e2e_postgres_reachable() -> bool:
    if getattr(_e2e_postgres_reachable, "_cached", None) is not None:  # pragma: no cover
        return _e2e_postgres_reachable._cached
    engine = create_engine(E2E_DATABASE_URL, connect_args={"connect_timeout": 2})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        _e2e_postgres_reachable._cached = False
        return False
    finally:
        engine.dispose()
    _e2e_postgres_reachable._cached = True
    return True


def pytest_collection_modifyitems(config, items) -> None:
    """Salta en colección los tests `e2e` cuando postgres-test (5434) no
    responde — antes de que los fixtures session-scoped (drop/create) intenten
    conectar y produzcan ERROR. Mismo patrón que el hook del conftest global,
    pero contra la base de test (no la de desarrollo)."""
    e2e_items = [item for item in items if item.get_closest_marker("e2e")]
    if not e2e_items or _e2e_postgres_reachable():
        return
    skip_marker = pytest.mark.skip(reason="postgres-test (5434) no disponible (marcador e2e)")
    for item in e2e_items:
        item.add_marker(skip_marker)


@pytest.fixture(autouse=True)
def _skip_db_tests_without_postgres(request) -> None:
    """Override del fixture homónimo del conftest global: los tests de este
    directorio dependen de postgres-test (5434), no de la base de desarrollo."""
    if not (
        request.node.get_closest_marker("db")
        or request.node.get_closest_marker("e2e")
    ):
        return
    if not _e2e_postgres_reachable():
        pytest.skip("postgres-test (5434) no disponible (marcador e2e)")


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures de base de datos E2E (reset por corrida + seed)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def e2e_engine():
    """Engine contra postgres-test con schema recreado (drop/create) por corrida."""
    engine = create_engine(E2E_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def e2e_session_factory(e2e_engine):
    return sessionmaker(
        bind=e2e_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )


@pytest.fixture()
def e2e_session(e2e_session_factory) -> Generator[Session, None, None]:
    with e2e_session_factory() as session:
        yield session


@pytest.fixture(scope="session")
def seed_ids(e2e_engine) -> dict:
    """Siembra los datos E2E sobre el schema recién creado. Expone los ids."""
    session_factory = sessionmaker(
        bind=e2e_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        result = seed(session)
        assert result["seeded"] is True, "El seed E2E no se aplicó sobre el schema vacío"
        session.commit()
        return result


# ═══════════════════════════════════════════════════════════════════════════
# TestClient contra la app real
# ═══════════════════════════════════════════════════════════════════════════


def _point_app_at_e2e_db() -> None:
    """Apunta settings y el engine de sesión de la app al PostgreSQL de test.

    Debe ejecutarse ANTES del primer import de `backend.app.main`: el engine
    de `backend.app.infrastructure.db.session` se crea al importar ese módulo.
    Si otro test del mismo proceso ya lo importó, se recrea el engine.
    """
    os.environ["DATABASE_URL"] = E2E_DATABASE_URL
    from backend.app.core.config import settings

    settings.database_url = E2E_DATABASE_URL

    session_mod = sys.modules.get("backend.app.infrastructure.db.session")
    if session_mod is not None:
        session_mod.engine.dispose()
        session_mod.engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
        session_mod.SessionLocal = sessionmaker(
            bind=session_mod.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )


@pytest.fixture(scope="session")
def client(seed_ids):
    """TestClient de la app real. El lifespan arranca el scheduler, cuyos jobs
    (intervalo mínimo 30s) no llegan a ejecutarse durante la suite; además las
    colas están vacías, así que no hay llamadas a servicios externos."""
    _point_app_at_e2e_db()
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client
