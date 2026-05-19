import json

from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.core.session_summarizer import HeuristicSessionSummarizer, LLMSessionSummarizer
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import ProviderChunk, ProviderHealth, ProviderRequest, ProviderResponse
from thoth.domain.session_compaction import SessionSummary


class CapturingProvider:
    def __init__(self, *, response_text: str) -> None:
        self._response_text = response_text
        self._initialized = False
        self.last_request: ProviderRequest | None = None

    def initialize(self, context: dict[str, object]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self.last_request = request
        return ProviderResponse(
            request_id=request.request_id,
            output_text=self._response_text,
            messages=[
                RuntimeMessage(
                    role=RuntimeMessageRole.ASSISTANT,
                    content=self._response_text,
                )
            ],
        )

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        _ = request
        return [ProviderChunk(request_id="req", index=0, content_delta="done", done=True)]

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized)


def test_heuristic_summarizer_merges_structured_data() -> None:
    summarizer = HeuristicSessionSummarizer()
    previous = SessionSummary(
        version=1,
        short="old",
        structured={
            "facts": ["fato antigo"],
            "goals": [],
            "decisions": [],
            "open_tasks": [],
        },
    )

    summary = summarizer.summarize(
        previous_summary=previous,
        compacted_history=[
            {
                "role": "user",
                "content": "quero implementar a camada 4",
                "request_id": "r1",
                "timestamp": "t",
            },
            {
                "role": "assistant",
                "content": "feito, decisao aplicada",
                "request_id": "r1",
                "timestamp": "t",
            },
        ],
        max_summary_chars=300,
    )

    assert "fato antigo" in summary.structured["facts"]
    assert summary.structured["goals"]
    assert summary.structured["decisions"]
    assert summary.short


def test_heuristic_summarizer_truncates_short_summary() -> None:
    summarizer = HeuristicSessionSummarizer()

    long_content = "x" * 500
    summary = summarizer.summarize(
        previous_summary=SessionSummary(),
        compacted_history=[
            {"role": "user", "content": long_content, "request_id": "r1", "timestamp": "t"}
        ],
        max_summary_chars=80,
    )

    assert len(summary.short) <= 80


def test_llm_summarizer_uses_selected_provider_and_model() -> None:
    provider = CapturingProvider(
        response_text=json.dumps(
            {
                "short": "summary from llm",
                "structured": {
                    "facts": ["f1"],
                    "goals": ["g1"],
                    "decisions": [],
                    "open_tasks": [],
                },
            }
        )
    )
    provider.initialize({"mode": "test"})

    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.summary",
        provider=provider,
        manifest=ProviderManifest(
            schema_version="v1",
            type="provider",
            name="mock.summary",
            version="0.1.0",
            entrypoint="x:y",
            capabilities={"chat_completion": True},
            compatibility={},
            metadata={},
        ),
    )
    selector = ProviderSelector(registry)
    summarizer = LLMSessionSummarizer(
        provider_selector=selector,
        provider_selection=ProviderSelectionConfig(preferred_provider="mock.summary"),
        model="summary-model-v1",
    )

    summary = summarizer.summarize(
        previous_summary=SessionSummary(),
        compacted_history=[
            {
                "role": "user",
                "content": "preciso de compactacao",
                "request_id": "r2",
                "timestamp": "t",
            }
        ],
        max_summary_chars=300,
    )

    assert summary.short == "summary from llm"
    assert summary.structured["goals"] == ["g1"]
    assert provider.last_request is not None
    assert provider.last_request.model == "summary-model-v1"


def test_llm_summarizer_falls_back_when_llm_returns_invalid_json() -> None:
    provider = CapturingProvider(response_text="not-json")
    provider.initialize({"mode": "test"})

    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.summary",
        provider=provider,
        manifest=ProviderManifest(
            schema_version="v1",
            type="provider",
            name="mock.summary",
            version="0.1.0",
            entrypoint="x:y",
            capabilities={"chat_completion": True},
            compatibility={},
            metadata={},
        ),
    )
    selector = ProviderSelector(registry)
    summarizer = LLMSessionSummarizer(provider_selector=selector)

    summary = summarizer.summarize(
        previous_summary=SessionSummary(),
        compacted_history=[
            {
                "role": "user",
                "content": "preciso de compactacao",
                "request_id": "r2",
                "timestamp": "t",
            }
        ],
        max_summary_chars=300,
    )

    assert summary.short
    assert summary.structured["goals"] or summary.structured["facts"]
