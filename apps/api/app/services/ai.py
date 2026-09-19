"""Provider-neutral conversation generation. Provider credentials never cross this boundary."""
from collections.abc import Sequence
from dataclasses import dataclass
import logging
from typing import Protocol
import httpx
from google import genai
from google.genai import types
from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


class AIServiceError(Exception):
    """Safe domain error that can be translated at the HTTP boundary."""


class AIProviderNotConfigured(AIServiceError):
    pass


class AIProviderUnavailable(AIServiceError):
    pass


class ConversationAIService(Protocol):
    def respond(self, messages: Sequence[ChatTurn]) -> str: ...


class AIProvider(ConversationAIService, Protocol):
    name: str


class NotConfiguredAIService:
    """Defers configuration errors until the HTTP route can return a safe chat state."""

    def __init__(self, reason: str):
        self.reason = reason

    def respond(self, messages: Sequence[ChatTurn]) -> str:
        raise AIProviderNotConfigured(self.reason)


class OpenAIResponsesService:
    """Minimal adapter for OpenAI's server-side Responses API."""
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def respond(self, messages: Sequence[ChatTurn]) -> str:
        if not self.settings.openai_api_key:
            raise AIProviderNotConfigured("No AI provider API key is configured.")
        payload = {
            "model": self.settings.ai_model,
            "store": False,
            "instructions": "You are ULTRON, a precise and helpful personal AI assistant.",
            "input": [{"role": turn.role, "content": turn.content} for turn in messages],
        }
        try:
            if self.client:
                response = self.client.post(self.endpoint, json=payload, headers=self._headers())
            else:
                with httpx.Client(timeout=httpx.Timeout(self.settings.ai_timeout_seconds)) as client:
                    response = client.post(self.endpoint, json=payload, headers=self._headers())
            response.raise_for_status()
            text = response.json().get("output_text", "").strip()
            if not text:
                raise AIProviderUnavailable("The provider returned no text output.")
            return text
        except httpx.TimeoutException as error:
            raise AIProviderUnavailable("The AI provider timed out.") from error
        except httpx.HTTPStatusError as error:
            raise AIProviderUnavailable("The AI provider rejected or could not process the request.") from error
        except httpx.HTTPError as error:
            raise AIProviderUnavailable("The AI provider is unavailable.") from error

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}


class GeminiProvider:
    """Google GenAI SDK adapter for Gemini's server-side generate-content API."""

    name = "Gemini"


    def __init__(self, settings: Settings, client: object | None = None):
        self.settings = settings
        self.client = client if client is not None else (genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None)

    def respond(self, messages: Sequence[ChatTurn]) -> str:
        if not self.settings.gemini_api_key or not self.client:
            raise AIProviderNotConfigured("No Gemini API key is configured.")
        contents = [
            types.Content(
                role="model" if turn.role == "assistant" else "user",
                parts=[types.Part(text=turn.content)],
            )
            for turn in messages
        ]
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model or self.settings.ai_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction="You are ULTRON, a precise and helpful personal AI assistant."
                ),
            )
            text = (getattr(response, "text", None) or "").strip()
            if not text:
                raise AIProviderUnavailable("The Gemini provider returned no text output.")
            return text
        except AIProviderUnavailable:
            raise
        except Exception as error:
            raise AIProviderUnavailable("The Gemini provider is unavailable.") from error


# Preserve the established service name for callers and injected-client tests.
GeminiService = GeminiProvider


class OpenAICompatibleProvider:
    """Small shared adapter for OpenAI-compatible fallback APIs."""
    endpoint = ""
    name = "provider"

    def __init__(self, api_key: str | None, model: str, timeout: float, client: httpx.Client | None = None):
        self.api_key, self.model, self.timeout, self.client = api_key, model, timeout, client

    def respond(self, messages: Sequence[ChatTurn]) -> str:
        if not self.api_key:
            raise AIProviderNotConfigured(f"No {self.name} API key is configured.")
        payload = {"model": self.model, "messages": [{"role": turn.role, "content": turn.content} for turn in messages]}
        try:
            if self.client:
                response = self.client.post(self.endpoint, json=payload, headers=self._headers())
            else:
                with httpx.Client(timeout=httpx.Timeout(self.timeout)) as client:
                    response = client.post(self.endpoint, json=payload, headers=self._headers())
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"].strip()
            if not text:
                raise AIProviderUnavailable(f"The {self.name} provider returned no text output.")
            return text
        except AIProviderUnavailable:
            raise
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise AIProviderUnavailable(f"The {self.name} provider returned an invalid response.") from error
        except httpx.TimeoutException as error:
            raise AIProviderUnavailable(f"The {self.name} provider timed out.") from error
        except httpx.HTTPStatusError as error:
            raise AIProviderUnavailable(f"The {self.name} provider is temporarily unavailable.") from error
        except httpx.HTTPError as error:
            raise AIProviderUnavailable(f"The {self.name} provider is unavailable.") from error

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}


class GroqProvider(OpenAICompatibleProvider):
    endpoint = "https://api.groq.com/openai/v1/chat/completions"
    name = "Groq"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        super().__init__(settings.groq_api_key, settings.groq_model, settings.ai_timeout_seconds, client)


class OpenRouterProvider(OpenAICompatibleProvider):
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    name = "OpenRouter"

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        super().__init__(settings.openrouter_api_key, settings.openrouter_model, settings.ai_timeout_seconds, client)


class AIRouter:
    """Bounded primary/fallback router; provider errors never leak to clients."""
    def __init__(self, providers: Sequence[AIProvider], primary_retries: int = 1):
        self.providers, self.primary_retries = list(providers), primary_retries

    def respond(self, messages: Sequence[ChatTurn]) -> str:
        configured = False
        for index, provider in enumerate(self.providers):
            attempts = 1 + self.primary_retries if index == 0 else 1
            for attempt in range(attempts):
                try:
                    text = provider.respond(messages)
                    configured = True
                    logger.info("AI provider selected: %s", provider.name)
                    return text
                except AIProviderNotConfigured:
                    logger.info("AI provider skipped (not configured): %s", provider.name)
                    break
                except AIProviderUnavailable:
                    configured = True
                    logger.warning("AI provider unavailable: %s (attempt %s/%s)", provider.name, attempt + 1, attempts)
            if index < len(self.providers) - 1:
                logger.info("AI provider fallback from %s", provider.name)
        if not configured:
            raise AIProviderNotConfigured("No AI provider is configured.")
        raise AIProviderUnavailable("AI providers are temporarily unavailable. Please try again.")


def create_ai_service(settings: Settings) -> ConversationAIService:
    if settings.ai_provider == "gemini":
        return AIRouter([GeminiProvider(settings), GroqProvider(settings), OpenRouterProvider(settings)])
    if settings.ai_provider == "openai":
        return OpenAIResponsesService(settings)
    return NotConfiguredAIService("The configured AI provider is not supported.")


def get_ai_service() -> ConversationAIService:
    return create_ai_service(get_settings())
