import logging

from typing import Protocol

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def complete(self, system: str, user: str, temperature: float = 0.1) -> str: ...

    def chat_complete(self, messages: list[dict], temperature: float = 0.1) -> str: ...

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

    def chat_complete(self, messages: list[dict], temperature: float = 0.1) -> str:
        full_text = " ".join(m.get("content", "") for m in messages)
        self.calls.append({"messages": messages})
        for key, resp in self.responses.items():
            if key.lower() in full_text.lower():
                return resp
        return '{"action": "direct"}'


class DeepSeekProvider:
    """DeepSeek LLM via OpenAI-compatible API."""

    name = "deepseek"

    def __init__(self) -> None:
        from backend.app.core.config import settings

        self.api_key = settings.deepseek_api_key or ""
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model

    def _call(self, messages: list[dict], temperature: float) -> str:
        import openai

        from openai import OpenAI  # type: ignore[import]

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                timeout=30,
            )
            return resp.choices[0].message.content or ""
        except openai.APIConnectionError:
            logger.warning("DeepSeek API connection error")
            return "Lo siento, no pude conectarme con el servicio de IA."
        except openai.RateLimitError:
            logger.warning("DeepSeek API rate limit exceeded")
            return "El servicio de IA está temporalmente sobrecargado. Intentá de nuevo en unos segundos."
        except openai.AuthenticationError:
            logger.error("DeepSeek API key is invalid or missing")
            return "Error de configuración del servicio de IA."
        except openai.APIStatusError as exc:
            logger.warning("DeepSeek API status error: %s", exc)
            return "El servicio de IA respondió con un error. Intentá de nuevo."
        except Exception:
            logger.exception("Unexpected DeepSeek API error")
            return "Ocurrió un error inesperado al procesar tu consulta."

    def complete(self, system: str, user: str, temperature: float = 0.1) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self._call(messages, temperature)

    def chat_complete(self, messages: list[dict], temperature: float = 0.1) -> str:
        return self._call(messages, temperature)
