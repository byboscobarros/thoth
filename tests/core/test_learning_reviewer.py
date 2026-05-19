import json

from thoth.core.learning_reviewer import LLMLearningReviewer
from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import ProviderChunk, ProviderHealth, ProviderRequest, ProviderResponse


class StaticResponseProvider:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self._initialized = False

    def initialize(self, context: dict[str, object]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(request_id=request.request_id, output_text=self._response_text)

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        _ = request
        return [ProviderChunk(request_id="req", index=0, content_delta="ok", done=True)]

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized)


def test_learning_reviewer_extracts_suggestions_from_json() -> None:
    provider = StaticResponseProvider(
        json.dumps(
            {
                "memories": [
                    "Usuario prefere respostas objetivas",
                    "Usuario valoriza arquitetura modular",
                ]
            }
        )
    )
    provider.initialize({"mode": "test"})

    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.review",
        provider=provider,
        manifest=ProviderManifest(
            schema_version="v1",
            type="provider",
            name="mock.review",
            version="0.1.0",
            entrypoint="x:y",
            capabilities={"chat_completion": True},
            compatibility={},
            metadata={},
        ),
    )

    reviewer = LLMLearningReviewer(
        provider_selector=ProviderSelector(registry),
        provider_selection=ProviderSelectionConfig(preferred_provider="mock.review"),
    )

    suggestions = reviewer.review(
        request_id="req_1",
        session_id="sess_1",
        input_messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="prefiro objetividade")],
        assistant_message="ok",
    )

    assert len(suggestions) == 2
    assert "Usuario prefere respostas objetivas" in suggestions


def test_learning_reviewer_returns_empty_on_invalid_json() -> None:
    provider = StaticResponseProvider("not-json")
    provider.initialize({"mode": "test"})

    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.review",
        provider=provider,
        manifest=ProviderManifest(
            schema_version="v1",
            type="provider",
            name="mock.review",
            version="0.1.0",
            entrypoint="x:y",
            capabilities={"chat_completion": True},
            compatibility={},
            metadata={},
        ),
    )

    reviewer = LLMLearningReviewer(
        provider_selector=ProviderSelector(registry),
        provider_selection=ProviderSelectionConfig(preferred_provider="mock.review"),
    )

    suggestions = reviewer.review(
        request_id="req_2",
        session_id="sess_2",
        input_messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="x")],
        assistant_message="y",
    )

    assert suggestions == []
