"""PromptBuilder — enriches SQL Agent prompts with few-shot examples."""

from __future__ import annotations

from backend.app.application.telegram.sql_agent.example_store import ExampleStore


_FEW_SHOT_TEMPLATE = """### Ejemplo {idx}
Pregunta: {question}
SQL:
```sql
{sql}
```
"""


class PromptBuilder:
    """Retrieves similar examples from the vector store and formats them
    for injection into the QueryGenerator prompt.
    """

    def __init__(self, store: ExampleStore | None = None) -> None:
        self._store = store

    def build_few_shot(self, user_text: str, k: int = 3) -> str:
        """Return a formatted few-shot block for *user_text*, or empty string
        if the store is empty / unavailable.
        """
        if self._store is None or self._store.count() == 0:
            return ""

        examples = self._store.search(user_text, k=k)
        if not examples:
            return ""

        blocks = []
        for i, ex in enumerate(examples, start=1):
            blocks.append(
                _FEW_SHOT_TEMPLATE.format(
                    idx=i,
                    question=ex.nl_query,
                    sql=ex.sql,
                )
            )
        return "\n".join(blocks)

    @staticmethod
    def wrap_prompt(
        base_prompt: str,
        few_shot_block: str,
        separator: str = "\n\n---\n\n",
    ) -> str:
        """Insert the few-shot block before the final user question in a prompt."""
        if not few_shot_block:
            return base_prompt
        return f"{few_shot_block}{separator}{base_prompt}"
