"""Provider-neutral conversation generation. Provider credentials never cross this boundary."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
import httpx
from google import genai
from google.genai import types
from ..config import Settings, get_settings


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


class GeminiService:
    """Google GenAI SDK adapter for Gemini's server-side generate-content API."""

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
                model=self.settings.ai_model,
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


def create_ai_service(settings: Settings) -> ConversationAIService:
    if settings.ai_provider == "gemini":
        return GeminiService(settings)
    if settings.ai_provider == "openai":
        return OpenAIResponsesService(settings)
    return NotConfiguredAIService("The configured AI provider is not supported.")


def get_ai_service() -> ConversationAIService:
    return create_ai_service(get_settings())
