from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, system: str, user: str, temperature: float = 0.1) -> str: ...

    @property
    def name(self) -> str: ...


class FakeLLMProvider:
    """Returns scripted responses for testing. Responses keyed by substring match."""

    name = "fake"

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        # responses: {substring_to_match: response_text}
        self.responses = responses or {}
        self.calls: list[dict] = []  # record calls for test assertions

    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        self.calls.append({"system": system, "user": user})
        for key, resp in self.responses.items():
            if key.lower() in user.lower():
                return resp
        return '{"intent": "out_of_domain", "entities": {}, "confidence": 0.0}'


class DeepSeekProvider:
    """DeepSeek LLM via OpenAI-compatible API."""

    name = "deepseek"

    def __init__(self) -> None:
        import os

        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        from openai import OpenAI  # type: ignore[import]

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
