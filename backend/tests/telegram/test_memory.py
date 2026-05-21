"""Tests for MemoryManager — conversation history loading."""

import time
import uuid
from datetime import UTC, datetime, timedelta

from backend.app.application.telegram.memory import MemoryManager, SessionState, SessionStore
from backend.app.infrastructure.db.models.telegram import TelegramInteractionModel
from backend.app.infrastructure.repositories.telegram import TelegramRepository


def _add_interaction(
    db_session,
    *,
    telegram_user_id: str,
    input_text: str,
    response_text: str,
    created_at: datetime | None = None,
) -> None:
    """Helper: agrega una interacción de Telegram al DB de prueba."""
    interaction = TelegramInteractionModel(
        id=str(uuid.uuid4()),
        telegram_user_id=telegram_user_id,
        matched_user_id=None,
        user_role=None,
        intent_id="test",
        input_text=input_text,
        extracted_entities=None,
        intent_confidence=None,
        tool_name=None,
        tool_request=None,
        tool_response=None,
        response_text=response_text,
        cache_status=None,
        fallback_reason=None,
        status="completed",
        created_at=created_at if created_at is not None else datetime.now(UTC),
    )
    db_session.add(interaction)
    db_session.flush()


def test_load_history_empty_db(db_session) -> None:
    """Sin interacciones previas → lista vacía."""
    memory = MemoryManager(TelegramRepository(db_session))
    history = memory.load_history("tg-nonexistent")
    assert history == []


def test_load_history_returns_chronological_pairs(db_session) -> None:
    """Con 2 interacciones → devuelve 4 mensajes en orden user/assistant/user/assistant."""
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    base_time = datetime.now(UTC)
    _add_interaction(
        db_session,
        telegram_user_id=tg_id,
        input_text="Hola",
        response_text="¡Hola!",
        created_at=base_time,
    )
    _add_interaction(
        db_session,
        telegram_user_id=tg_id,
        input_text="¿Qué hay?",
        response_text="Todo bien.",
        created_at=base_time + timedelta(seconds=1),
    )

    memory = MemoryManager(TelegramRepository(db_session))
    history = memory.load_history(tg_id)

    assert len(history) == 4
    assert history[0] == {"role": "user", "content": "Hola"}
    assert history[1] == {"role": "assistant", "content": "¡Hola!"}
    assert history[2] == {"role": "user", "content": "¿Qué hay?"}
    assert history[3] == {"role": "assistant", "content": "Todo bien."}


def test_load_history_respects_limit(db_session) -> None:
    """Con 5 interacciones y limit=3 → solo 6 mensajes (3 pares)."""
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    base_time = datetime.now(UTC)
    for i in range(5):
        _add_interaction(
            db_session,
            telegram_user_id=tg_id,
            input_text=f"Mensaje {i}",
            response_text=f"Respuesta {i}",
            created_at=base_time + timedelta(seconds=i),
        )

    memory = MemoryManager(TelegramRepository(db_session))
    history = memory.load_history(tg_id, limit=3)

    assert len(history) == 6  # 3 pares × 2 mensajes cada uno


def test_load_history_ignores_other_users(db_session) -> None:
    """Las interacciones de otro telegram_user_id no aparecen en el historial."""
    tg_id_a = f"tg-{uuid.uuid4().hex[:8]}"
    tg_id_b = f"tg-{uuid.uuid4().hex[:8]}"
    _add_interaction(
        db_session,
        telegram_user_id=tg_id_a,
        input_text="A habla",
        response_text="A resp",
    )
    _add_interaction(
        db_session,
        telegram_user_id=tg_id_b,
        input_text="B habla",
        response_text="B resp",
    )

    memory = MemoryManager(TelegramRepository(db_session))
    history_a = memory.load_history(tg_id_a)

    assert len(history_a) == 2
    assert history_a[0]["content"] == "A habla"


# ---------------------------------------------------------------------------
# SessionStore tests
# ---------------------------------------------------------------------------

def test_session_store_set_and_get() -> None:
    """SessionStore guarda y recupera estado por telegram_user_id."""
    store = SessionStore(ttl_seconds=3600)
    state = SessionState(
        last_query_type="count_doctors_total",
        last_params={},
        last_results=[{"name": "Dr. Test"}],
    )
    store.set("tg-abc", state)
    retrieved = store.get("tg-abc")
    assert retrieved is not None
    assert retrieved.last_query_type == "count_doctors_total"
    assert retrieved.last_results == [{"name": "Dr. Test"}]


def test_session_store_get_nonexistent() -> None:
    """Usuario sin sesión → None."""
    store = SessionStore()
    assert store.get("tg-ghost") is None


def test_session_store_ttl_expiry() -> None:
    """Sesión expirada → None."""
    store = SessionStore(ttl_seconds=0)  # expire immediately
    state = SessionState(last_query_type="q")
    store.set("tg-xyz", state)
    time.sleep(0.01)  # let TTL pass
    assert store.get("tg-xyz") is None


def test_session_store_overwrite() -> None:
    """Segundo set() sobreescribe el estado anterior."""
    store = SessionStore()
    s1 = SessionState(last_query_type="q1")
    s2 = SessionState(last_query_type="q2")
    store.set("tg-a", s1)
    store.set("tg-a", s2)
    assert store.get("tg-a").last_query_type == "q2"


def test_session_store_clear_user() -> None:
    """clear() elimina la sesión de un usuario."""
    store = SessionStore()
    store.set("tg-b", SessionState(last_query_type="q"))
    store.clear("tg-b")
    assert store.get("tg-b") is None


def test_session_store_cleanup_expired() -> None:
    """cleanup_expired() elimina sesiones expiradas."""
    store = SessionStore(ttl_seconds=0)
    store.set("tg-old", SessionState(last_query_type="q"))
    time.sleep(0.01)
    store.cleanup_expired()
    assert store.get("tg-old") is None


# ---------------------------------------------------------------------------
# MemoryManager filtering tests
# ---------------------------------------------------------------------------


def test_memory_load_history_filters_formatted_responses(db_session) -> None:
    """Tool responses are skipped so internal summaries never leak to the LLM."""
    tg_id = f"tg-{uuid.uuid4().hex[:8]}"
    interaction = TelegramInteractionModel(
        id=str(uuid.uuid4()),
        telegram_user_id=tg_id,
        matched_user_id=None,
        user_role=None,
        intent_id="test",
        input_text="cuántos médicos hay",
        extracted_entities=None,
        intent_confidence=None,
        tool_name="count_doctors_total",
        tool_request=None,
        tool_response=None,
        response_text="Se encontraron 15 resultados:\n1. Dr. A\n2. Dr. B",
        cache_status=None,
        fallback_reason=None,
        status="completed",
        created_at=datetime.now(UTC),
    )
    db_session.add(interaction)
    db_session.flush()

    memory = MemoryManager(TelegramRepository(db_session))
    history = memory.load_history(tg_id)

    assert history == []
