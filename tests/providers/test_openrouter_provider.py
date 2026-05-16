import json

from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.provider_manifest import load_provider_manifest
from thoth.domain.providers import ProviderConfigurationError, ProviderRequest
from thoth.providers.openrouter.components.completion import OpenRouterCompletionComponent
from thoth.providers.openrouter.components.streaming import OpenRouterStreamingComponent
from thoth.providers.openrouter.provider import OpenRouterProvider


class _FakeResponse:
    def __init__(self, *, body: str | None = None, lines: list[str] | None = None) -> None:
        self._body = (body or "").encode("utf-8")
        self._lines = [(line + "\n").encode("utf-8") for line in (lines or [])]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type, exc, tb

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        return iter(self._lines)


def test_openrouter_manifest_is_valid() -> None:
    manifest = load_provider_manifest("src/thoth/providers/openrouter/manifest.json")

    assert manifest.name == "openrouter"
    assert manifest.capabilities["chat_completion"] is True
    assert manifest.capabilities["streaming"] is True


def test_openrouter_provider_requires_initialize_before_execute() -> None:
    provider = OpenRouterProvider()
    request = ProviderRequest(
        request_id="req_openrouter",
        messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
    )

    try:
        provider.execute(request)
    except ProviderConfigurationError as exc:
        assert exc.code == "provider.openrouter.not_initialized"
    else:
        raise AssertionError("Expected ProviderConfigurationError")


def test_openrouter_provider_is_unhealthy_without_api_key(monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_OPENROUTER_API_KEY", "")  # type: ignore[attr-defined]

    provider = OpenRouterProvider()
    provider.initialize({"mode": "test"})

    health = provider.healthcheck()
    assert health.ok is False

    request = ProviderRequest(
        request_id="req_openrouter_no_key",
        messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
    )

    try:
        provider.execute(request)
    except ProviderConfigurationError as exc:
        assert exc.code == "provider.openrouter.not_configured"
    else:
        raise AssertionError("Expected ProviderConfigurationError")


def test_openrouter_completion_maps_response_payload() -> None:
    captured_request: dict[str, object] = {}

    def fake_opener(request: object, timeout: float) -> _FakeResponse:
        captured_request["request"] = request
        captured_request["timeout"] = timeout
        body = json.dumps(
            {
                "id": "gen_123",
                "model": "openai/gpt-5.2",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "openrouter says hi",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 5,
                    "total_tokens": 17,
                },
            }
        )
        return _FakeResponse(body=body)

    component = OpenRouterCompletionComponent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.2",
        timeout_seconds=30.0,
        http_referer="https://thoth.local",
        app_title="Thoth",
        opener=fake_opener,
    )

    response = component.complete(
        ProviderRequest(
            request_id="req_completion",
            messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
            temperature=0.2,
            max_tokens=64,
        )
    )

    assert response.output_text == "openrouter says hi"
    assert response.usage == {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}
    assert response.metadata["provider"] == "openrouter"
    assert response.metadata["response_id"] == "gen_123"
    assert captured_request["timeout"] == 30.0


def test_openrouter_streaming_parses_sse_chunks() -> None:
    def fake_opener(request: object, timeout: float) -> _FakeResponse:
        _ = request, timeout
        return _FakeResponse(
            lines=[
                ': keep-alive comment',
                'data: {"choices":[{"delta":{"content":"hello "}}]}',
                'data: {"choices":[{"delta":{"content":"world"}}]}',
                'data: [DONE]',
            ]
        )

    component = OpenRouterStreamingComponent(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.2",
        timeout_seconds=30.0,
        opener=fake_opener,
    )

    chunks = component.stream(
        ProviderRequest(
            request_id="req_stream",
            messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="stream")],
        )
    )

    assert chunks[0].content_delta == "hello "
    assert chunks[1].content_delta == "world"
    assert chunks[-1].done is True
