import logging

from typing import Protocol

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def complete(self, system: str, user: str, temperature: float = 0.1) -> str: ...

    def chat_complete(self, messages: list[dict], temperature: float = 0.1, json_mode: bool = False) -> str: ...

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

    def chat_complete(self, messages: list[dict], temperature: float = 0.1, json_mode: bool = False) -> str:
        # Only search user messages, not system prompts, so response keys
        # don't accidentally match query-type descriptions in the system prompt.
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        self.calls.append({"messages": messages, "temperature": temperature, "json_mode": json_mode})
        for key, resp in self.responses.items():
            if key.lower() in user_text.lower():
                return resp
        return '{"action": "reply"}'


class DeepSeekProvider:
    """DeepSeek LLM via OpenAI-compatible API."""

    name = "deepseek"

    def __init__(self) -> None:
        from backend.app.core.config import settings

        self.api_key = settings.deepseek_api_key or ""
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model

    def _call(self, messages: list[dict], temperature: float, json_mode: bool = False) -> str:
        import openai

        from openai import OpenAI  # type: ignore[import]

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": 30,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
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

    def chat_complete(self, messages: list[dict], temperature: float = 0.1, json_mode: bool = False) -> str:
        return self._call(messages, temperature, json_mode=json_mode)
