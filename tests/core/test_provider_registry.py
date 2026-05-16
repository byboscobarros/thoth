from __future__ import annotations

from thoth.core.provider_registry import ProviderRegistry
from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import (
    ProviderChunk,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)


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
        return ProviderHealth(ok=self._ok, details="ready" if self._ok else "down")


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


def test_register_and_get_provider() -> None:
    registry = ProviderRegistry()

    registry.register(
        provider_id="mock.primary",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="mock", capabilities={"chat_completion": True}),
    )

    entry = registry.get("mock.primary")
    assert entry is not None
    assert entry.provider_id == "mock.primary"
    assert entry.health.ok is True


def test_list_by_capability_and_health() -> None:
    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.a",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="a", capabilities={"chat_completion": True, "streaming": False}),
    )
    registry.register(
        provider_id="mock.b",
        provider=FakeProvider(ok=False),
        manifest=_manifest(name="b", capabilities={"chat_completion": False, "streaming": True}),
    )

    chat_entries = registry.list_by_capability("chat_completion")
    stream_entries = registry.list_by_capability("streaming")
    healthy = registry.list_by_health(True)
    unhealthy = registry.list_by_health(False)

    assert [entry.provider_id for entry in chat_entries] == ["mock.a"]
    assert [entry.provider_id for entry in stream_entries] == ["mock.b"]
    assert [entry.provider_id for entry in healthy] == ["mock.a"]
    assert [entry.provider_id for entry in unhealthy] == ["mock.b"]


def test_update_health_reindexes_provider() -> None:
    registry = ProviderRegistry()
    registry.register(
        provider_id="mock.health",
        provider=FakeProvider(ok=True),
        manifest=_manifest(name="health", capabilities={"chat_completion": True}),
    )

    registry.update_health("mock.health", ProviderHealth(ok=False, details="offline"))

    assert [entry.provider_id for entry in registry.list_by_health(True)] == []
    assert [entry.provider_id for entry in registry.list_by_health(False)] == ["mock.health"]


def test_register_duplicate_provider_raises() -> None:
    registry = ProviderRegistry()
    manifest = _manifest(name="dup", capabilities={"chat_completion": True})
    registry.register(provider_id="mock.dup", provider=FakeProvider(ok=True), manifest=manifest)

    try:
        registry.register(provider_id="mock.dup", provider=FakeProvider(ok=True), manifest=manifest)
    except ValueError as exc:
        assert str(exc) == "provider already registered: mock.dup"
    else:
        assert False, "Expected ValueError"
