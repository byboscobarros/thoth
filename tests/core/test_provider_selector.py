from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import ProviderChunk, ProviderExecutionError, ProviderHealth, ProviderRequest, ProviderResponse


class FakeProvider:
    def __init__(self, *, ok: bool) -> None:
        self._ok = ok

    def initialize(self, context: dict[str, object]) -> None:
        _ = context

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(request_id=request.request_id, output_text="ok")

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        return [ProviderChunk(request_id=request.request_id, index=0, content_delta="ok", done=True)]

    def shutdown(self) -> None:
        return None

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._ok)


def _manifest(*, name: str, capabilities: dict[str, bool]) -> ProviderManifest:
    return ProviderManifest(
        schema_version="v1",
        type="provider",
        name=name,
        version="0.1.0",
        entrypoint="x:y",
        capabilities=capabilities,
        compatibility={},
        metadata={},
    )


def test_selector_uses_preferred_provider_when_eligible() -> None:
    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.default",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="default", capabilities={"chat_completion": True}),
    )
    registry.register(
        provider_id="mock.preferred",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="preferred", capabilities={"chat_completion": True}),
    )

    selector = ProviderSelector(registry)
    selected = selector.select(
        capability="chat_completion",
        config=ProviderSelectionConfig(preferred_provider="mock.preferred"),
    )

    assert selected.provider_id == "mock.preferred"


def test_selector_fallbacks_when_preferred_unhealthy() -> None:
    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.a",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="a", capabilities={"chat_completion": True}),
    )
    registry.register(
        provider_id="mock.b",
        provider=FakeProvider(ok=False),
        manifest=_manifest(name="b", capabilities={"chat_completion": True}),
    )

    selector = ProviderSelector(registry)
    selected = selector.select(
        capability="chat_completion",
        config=ProviderSelectionConfig(preferred_provider="mock.b"),
    )

    assert selected.provider_id == "mock.a"


def test_selector_can_select_unhealthy_when_config_allows() -> None:
    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.only",
        provider=FakeProvider(ok=False),
        manifest=_manifest(name="only", capabilities={"chat_completion": True}),
    )

    selector = ProviderSelector(registry)
    selected = selector.select(
        capability="chat_completion",
        config=ProviderSelectionConfig(require_healthy=False),
    )

    assert selected.provider_id == "mock.only"


def test_selector_raises_when_no_provider_available() -> None:
    registry = ProviderRegistry()
    selector = ProviderSelector(registry)

    try:
        selector.select(capability="chat_completion")
    except ProviderExecutionError as exc:
        assert exc.code == "provider.selection.unavailable"
    else:
        assert False, "Expected ProviderExecutionError"
