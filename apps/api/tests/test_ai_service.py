import json
import httpx
import pytest
from app.config import Settings
from app.services.ai import AIRouter, AIProviderNotConfigured, AIProviderUnavailable, ChatTurn, GeminiService, GroqProvider, NotConfiguredAIService, OpenAIResponsesService, OpenRouterProvider, create_ai_service


def test_provider_rejects_missing_server_key() -> None:
    service = OpenAIResponsesService(Settings(openai_api_key=None))
    with pytest.raises(AIProviderNotConfigured):
        service.respond([ChatTurn(role="user", content="Hello")])


def test_provider_returns_output_text_without_exposing_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert json.loads(request.content)["input"][-1]["content"] == "Hello"
        return httpx.Response(200, json={"output_text": "Hello from ULTRON."})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = OpenAIResponsesService(Settings(openai_api_key="test-secret"), client)
    assert service.respond([ChatTurn(role="user", content="Hello")]) == "Hello from ULTRON."


def test_provider_uses_safe_error_for_upstream_failure() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500, json={"error": {"message": "secret upstream detail"}})))
    service = OpenAIResponsesService(Settings(openai_api_key="test-secret"), client)
    with pytest.raises(AIProviderUnavailable) as error:
        service.respond([ChatTurn(role="user", content="Hello")])
    assert "secret" not in str(error.value)


class FakeGeminiModels:
    def __init__(self, result: object | Exception):
        self.result = result
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeGeminiClient:
    def __init__(self, result: object | Exception):
        self.models = FakeGeminiModels(result)


def test_gemini_initializes_with_injected_client() -> None:
    client = FakeGeminiClient(type("Response", (), {"text": "Ready"})())
    service = GeminiService(Settings(gemini_api_key="test-gemini-key"), client)
    assert service.client is client


def test_provider_factory_defaults_to_gemini_and_keeps_openai_selectable() -> None:
    assert isinstance(create_ai_service(Settings(gemini_api_key="test-gemini-key")), AIRouter)
    assert isinstance(create_ai_service(Settings(ai_provider="openai", openai_api_key="test-openai-key")), OpenAIResponsesService)


def test_unknown_provider_returns_safe_configuration_service() -> None:
    service = create_ai_service(Settings(ai_provider="unknown"))
    assert isinstance(service, NotConfiguredAIService)
    with pytest.raises(AIProviderNotConfigured):
        service.respond([ChatTurn(role="user", content="Hello")])


def test_gemini_rejects_missing_key() -> None:
    service = GeminiService(Settings(gemini_api_key=None), FakeGeminiClient(type("Response", (), {"text": "unused"})()))
    with pytest.raises(AIProviderNotConfigured):
        service.respond([ChatTurn(role="user", content="Hello")])


def test_gemini_returns_mocked_provider_response() -> None:
    client = FakeGeminiClient(type("Response", (), {"text": "Hello from Gemini."})())
    service = GeminiService(Settings(gemini_api_key="test-gemini-key", ai_model="gemini-test"), client)
    assert service.respond([ChatTurn(role="user", content="Hello")]) == "Hello from Gemini."
    assert client.models.calls[0]["model"] == "gemini-test"
    assert client.models.calls[0]["contents"][-1].parts[0].text == "Hello"


def test_gemini_failure_is_safe_and_never_echoes_secret() -> None:
    client = FakeGeminiClient(RuntimeError("provider failure leaked-key-value"))
    service = GeminiService(Settings(gemini_api_key="leaked-key-value"), client)
    with pytest.raises(AIProviderUnavailable) as error:
        service.respond([ChatTurn(role="user", content="Hello")])
    assert "leaked-key-value" not in str(error.value)


class StubProvider:
    def __init__(self, name: str, result: str | Exception):
        self.name, self.result, self.calls = name, result, 0

    def respond(self, messages):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_router_returns_gemini_response_without_fallback() -> None:
    gemini, groq = StubProvider("Gemini", "Gemini response"), StubProvider("Groq", "Groq response")
    assert AIRouter([gemini, groq]).respond([ChatTurn(role="user", content="Hello")]) == "Gemini response"
    assert (gemini.calls, groq.calls) == (1, 0)


@pytest.mark.parametrize("failure", [AIProviderUnavailable("503"), AIProviderUnavailable("429"), AIProviderUnavailable("timeout")])
def test_router_retries_gemini_then_falls_back_to_groq(failure) -> None:
    gemini, groq = StubProvider("Gemini", failure), StubProvider("Groq", "Groq response")
    assert AIRouter([gemini, groq]).respond([ChatTurn(role="user", content="Hello")]) == "Groq response"
    assert (gemini.calls, groq.calls) == (2, 1)


def test_router_uses_openrouter_after_gemini_and_groq_fail() -> None:
    unavailable = AIProviderUnavailable("temporary failure")
    gemini, groq, openrouter = StubProvider("Gemini", unavailable), StubProvider("Groq", unavailable), StubProvider("OpenRouter", "OpenRouter response")
    assert AIRouter([gemini, groq, openrouter]).respond([ChatTurn(role="user", content="Hello")]) == "OpenRouter response"
    assert (gemini.calls, groq.calls, openrouter.calls) == (2, 1, 1)


def test_router_skips_missing_fallback_key_and_returns_controlled_error() -> None:
    unavailable = StubProvider("Gemini", AIProviderUnavailable("503"))
    missing = StubProvider("Groq", AIProviderNotConfigured("missing key"))
    with pytest.raises(AIProviderUnavailable, match="temporarily unavailable"):
        AIRouter([unavailable, missing]).respond([ChatTurn(role="user", content="Hello")])
    assert (unavailable.calls, missing.calls) == (2, 1)


def test_openai_compatible_providers_use_configured_models() -> None:
    settings = Settings(groq_api_key="groq-key", groq_model="groq-test", openrouter_api_key="router-key", openrouter_model="router-test")
    response = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})))
    assert GroqProvider(settings, response).respond([ChatTurn(role="user", content="Hello")]) == "OK"
    assert OpenRouterProvider(settings, response).respond([ChatTurn(role="user", content="Hello")]) == "OK"
