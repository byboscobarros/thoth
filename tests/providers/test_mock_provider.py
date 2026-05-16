from pathlib import Path

from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.provider_manifest import load_provider_manifest
from thoth.domain.providers import ProviderConfigurationError, ProviderRequest
from thoth.providers.mock.provider import MockProvider


def test_mock_provider_manifest_is_valid() -> None:
    manifest_path = Path("src/thoth/providers/mock/manifest.json")
    manifest = load_provider_manifest(manifest_path)

    assert manifest.name == "mock"
    assert manifest.capabilities["chat_completion"] is True


def test_mock_provider_execute_and_stream_are_deterministic() -> None:
    provider = MockProvider()
    provider.initialize({"mode": "test"})

    request = ProviderRequest(
        request_id="req_mock",
        messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
    )

    response = provider.execute(request)
    chunks = provider.stream(request)

    assert response.output_text == "[mock] echo: hello"
    assert chunks[0].content_delta == "[mock] "
    assert chunks[1].done is True


def test_mock_provider_requires_initialize_before_execute() -> None:
    provider = MockProvider()
    request = ProviderRequest(
        request_id="req_mock",
        messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
    )

    try:
        provider.execute(request)
    except ProviderConfigurationError as exc:
        assert exc.code == "provider.mock.not_initialized"
    else:
        assert False, "Expected ProviderConfigurationError"
