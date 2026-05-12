"""Conversation memory for the Telegram conversational agent."""

import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.infrastructure.repositories.telegram import TelegramRepository


@dataclass
class SessionState:
    """Conversation session state for follow-up resolution."""
    last_query_type: str | None = None
    last_params: dict[str, Any] | None = None
    last_results: list[dict[str, Any]] | None = None
    last_filters: dict[str, Any] | None = None
    last_tool_name: str | None = None
    last_agent_action: str | None = None
    last_operation: str | None = None
    last_total: int | None = None
    last_document_format: str | None = None
    pending_selection: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)


class SessionStore:
    """In-memory session state storage with TTL-based expiry."""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._store: dict[str, SessionState] = {}
        self._ttl = ttl_seconds

    def get(self, telegram_user_id: str) -> SessionState | None:
        """Return session state if it exists and is not expired."""
        state = self._store.get(telegram_user_id)
        if state is None:
            return None
        if time.time() - state.created_at > self._ttl:
            del self._store[telegram_user_id]
            return None
        return state

    def set(self, telegram_user_id: str, state: SessionState) -> None:
        """Store (or overwrite) session state."""
        state.created_at = time.time()
        self._store[telegram_user_id] = state

    def clear(self, telegram_user_id: str) -> None:
        """Remove session state for a user."""
        self._store.pop(telegram_user_id, None)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now = time.time()
        expired = [
            uid for uid, s in self._store.items()
            if now - s.created_at > self._ttl
        ]
        for uid in expired:
            del self._store[uid]
        return len(expired)


class MemoryManager:
    """Loads recent Telegram interactions as conversation history for LLM context."""

    def __init__(self, telegram_repo: TelegramRepository) -> None:
        self._telegram_repo = telegram_repo

    def load_history(
        self,
        telegram_user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Return last `limit` interactions as a conversation history list
        formatted for LLM chat completion (oldest first, chronological order).

        Returns:
            [{"role": "user", "content": "..."},
             {"role": "assistant", "content": "..."}, ...]
        """
        interactions = self._telegram_repo.list_interactions(
            telegram_user_id=telegram_user_id,
            limit=limit,
        )
        # list_interactions returns desc order; reverse for chronological
        interactions.reverse()

        _skip_prefixes = (
            "Lo siento, no pude",
            "El servicio de IA",
            "Error de configuración",
            "Ocurrió un error",
            "No pude encontrar",
        )

        history: list[dict] = []
        for interaction in interactions:
            response = interaction.response_text or ""
            tool_name = interaction.tool_name

            # Tool outputs are operational state, not conversational text.
            # Feeding placeholders like "[Acción ejecutada: ...]" back to the LLM
            # can make it echo them to the user on later questions.
            if tool_name:
                continue

            # Skip other non-conversational responses
            if any(response.startswith(p) for p in _skip_prefixes):
                continue

            history.append({"role": "user", "content": interaction.input_text})
            history.append({"role": "assistant", "content": response})

        return history
