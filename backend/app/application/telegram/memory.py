"""Conversation memory for the Telegram conversational agent."""

from backend.app.infrastructure.repositories.telegram import TelegramRepository


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

        history: list[dict] = []
        for interaction in interactions:
            history.append({"role": "user", "content": interaction.input_text})
            history.append(
                {"role": "assistant", "content": interaction.response_text}
            )
        return history
