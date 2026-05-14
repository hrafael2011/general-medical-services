"""Tests for DB-backed session persistence."""
import uuid

from backend.app.application.telegram.memory import SessionState, SessionStore
from backend.app.infrastructure.repositories.telegram import TelegramRepository


def test_persistent_session_store_survives_new_instance(db_session) -> None:
    """Session stored via one SessionStore instance is readable by another."""
    repo = TelegramRepository(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"

    store_a = SessionStore(ttl_seconds=3600, telegram_repo=repo)
    state = SessionState(
        last_query_type="count_doctors_total",
        last_params={"month": 6},
        last_results=[{"name": "Dr. A"}],
    )
    store_a.set(tg_id, state)

    # Simulate restart: new SessionStore instance
    db_session.expire_all()
    store_b = SessionStore(ttl_seconds=3600, telegram_repo=repo)
    retrieved = store_b.get(tg_id)

    assert retrieved is not None
    assert retrieved.last_query_type == "count_doctors_total"
    assert retrieved.last_params == {"month": 6}
    assert retrieved.last_results == [{"name": "Dr. A"}]


def test_persistent_session_store_overwrite(db_session) -> None:
    """Second set() overwrites the previously persisted state."""
    repo = TelegramRepository(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"

    store = SessionStore(ttl_seconds=3600, telegram_repo=repo)
    store.set(tg_id, SessionState(last_query_type="q1"))
    store.set(tg_id, SessionState(last_query_type="q2"))

    db_session.expire_all()
    retrieved = store.get(tg_id)
    assert retrieved.last_query_type == "q2"


def test_persistent_session_store_clear(db_session) -> None:
    """clear() removes from DB."""
    repo = TelegramRepository(db_session)
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"

    store = SessionStore(ttl_seconds=3600, telegram_repo=repo)
    store.set(tg_id, SessionState(last_query_type="q"))
    store.clear(tg_id)

    db_session.expire_all()
    assert store.get(tg_id) is None


def test_persistent_session_store_get_nonexistent(db_session) -> None:
    """Usuario sin sesion en DB -> None."""
    repo = TelegramRepository(db_session)
    store = SessionStore(ttl_seconds=3600, telegram_repo=repo)
    assert store.get("tg-ghost-persistent") is None


def test_in_memory_store_still_works_without_repo() -> None:
    """SessionStore sin telegram_repo funciona como antes (solo en memoria)."""
    store = SessionStore(ttl_seconds=3600)
    store.set("tg-test", SessionState(last_query_type="q"))
    retrieved = store.get("tg-test")
    assert retrieved is not None
    assert retrieved.last_query_type == "q"


def test_in_memory_store_clear() -> None:
    """clear en modo solo memoria funciona."""
    store = SessionStore()
    store.set("tg-clear", SessionState(last_query_type="x"))
    store.clear("tg-clear")
    assert store.get("tg-clear") is None
