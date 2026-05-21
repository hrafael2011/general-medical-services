"""Conversation memory for the Telegram conversational agent."""

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.infrastructure.repositories.telegram import TelegramRepository


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert datetime/date/Decimal to JSON-safe types."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    return obj


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
    last_domain: str | None = None
    last_period: dict[str, Any] | None = None
    last_subject: str | None = None
    last_total: int | None = None
    last_document_format: str | None = None
    pending_selection: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)


class SessionStore:
    """Session state storage with optional DB persistence.

    When *telegram_repo* is provided, sessions are persisted to the
    ``telegram_sessions`` table and survive server restarts.
    Without it, sessions live only in memory (backward compatible).
    """

    def __init__(
        self,
        ttl_seconds: int = 1800,
        telegram_repo=None,  # TelegramRepository | None
    ) -> None:
        self._store: dict[str, SessionState] = {}
        self._ttl = ttl_seconds
        self._telegram_repo = telegram_repo

    def get(self, telegram_user_id: str) -> SessionState | None:
        """Return session state if it exists and is not expired."""
        state = self._store.get(telegram_user_id)
        if state is None and self._telegram_repo is not None:
            raw = self._telegram_repo.get_session(telegram_user_id)
            if raw:
                state = SessionState(**raw)

        if state is None:
            return None
        if time.time() - state.created_at > self._ttl:
            self.clear(telegram_user_id)
            return None
        return state

    def set(self, telegram_user_id: str, state: SessionState) -> None:
        """Store (or overwrite) session state."""
        state.created_at = time.time()
        self._store[telegram_user_id] = state
        if self._telegram_repo is not None:
            self._telegram_repo.upsert_session(
                telegram_user_id,
                _sanitize_for_json({
                    "last_query_type": state.last_query_type,
                    "last_params": state.last_params,
                    "last_results": state.last_results,
                    "last_filters": state.last_filters,
                    "last_tool_name": state.last_tool_name,
                    "last_agent_action": state.last_agent_action,
                    "last_operation": state.last_operation,
                    "last_domain": state.last_domain,
                    "last_period": state.last_period,
                    "last_subject": state.last_subject,
                    "last_total": state.last_total,
                    "last_document_format": state.last_document_format,
                    "pending_selection": state.pending_selection,
                    "created_at": state.created_at,
                }),
            )

    def clear(self, telegram_user_id: str) -> None:
        """Remove session state for a user."""
        self._store.pop(telegram_user_id, None)
        if self._telegram_repo is not None:
            self._telegram_repo.delete_session(telegram_user_id)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now = time.time()
        expired = [
            uid for uid, s in self._store.items()
            if now - s.created_at > self._ttl
        ]
        for uid in expired:
            del self._store[uid]
            if self._telegram_repo is not None:
                self._telegram_repo.delete_session(uid)
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
