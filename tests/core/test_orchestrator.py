from thoth.core.event_bus import InMemoryEventBus
from thoth.core.orchestrator import RuntimeOrchestrator
from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelector
from thoth.core.session_manager import SessionManager
from thoth.core.session_store import InMemorySessionStore
from thoth.domain.envelopes import RuntimeInputEnvelope, RuntimeMessage, RuntimeMessageRole, RuntimeStatus
from thoth.domain.provider_manifest import ProviderManifest, load_provider_manifest
from thoth.domain.events import RuntimeEventType
from thoth.domain.providers import ProviderChunk, ProviderHealth, ProviderRequest, ProviderResponse
from thoth.providers.mock.provider import MockProvider


class CapturingProvider:
    def __init__(self) -> None:
        self._initialized = False
        self.seen_requests: list[ProviderRequest] = []

    def initialize(self, context: dict[str, object]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self.seen_requests.append(request)
        text = f"captured:{len(request.messages)}"
        return ProviderResponse(request_id=request.request_id, output_text=text)

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        self.seen_requests.append(request)
        return [ProviderChunk(request_id=request.request_id, index=0, content_delta="x", done=True)]

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized)


def test_handle_emits_required_events_and_persists_session_state() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    session_manager = SessionManager(session_store)
    orchestrator = RuntimeOrchestrator(session_manager=session_manager, event_bus=event_bus)

    response = orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_1",
            gateway="cli",
            session={"session_id": "sess_1"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
        )
    )

    assert response.request_id == "req_1"
    assert response.status is RuntimeStatus.SUCCESS
    assert response.audit_ref == "session:sess_1:rev:1"
    assert len(event_bus.published_events) == 2
    assert event_bus.published_events[0].type is RuntimeEventType.REQUEST_RECEIVED
    assert event_bus.published_events[1].type is RuntimeEventType.RESPONSE_EMITTED

    session = session_store.get("sess_1")
    assert session is not None
    assert session.revision == 1
    assert session.data["last_request_id"] == "req_1"
    history = session.data["message_history"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"
    assert history[1]["role"] == "assistant"


def test_handle_falls_back_to_request_based_session_id() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    session_manager = SessionManager(session_store)
    orchestrator = RuntimeOrchestrator(session_manager=session_manager, event_bus=event_bus)

    response = orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_2",
            gateway="cli",
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello")],
        )
    )

    assert response.audit_ref == "session:session:req_2:rev:1"
    assert session_store.get("session:req_2") is not None


def test_handle_appends_message_history_without_overwriting() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    session_manager = SessionManager(session_store)
    orchestrator = RuntimeOrchestrator(session_manager=session_manager, event_bus=event_bus)

    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_10",
            gateway="cli",
            session={"session_id": "sess_hist"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="first")],
        )
    )
    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_11",
            gateway="cli",
            session={"session_id": "sess_hist"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="second")],
        )
    )

    session = session_store.get("sess_hist")
    assert session is not None
    history = session.data["message_history"]
    assert len(history) == 4
    assert history[0]["request_id"] == "req_10"
    assert history[2]["request_id"] == "req_11"
    assert history[0]["content"] == "first"
    assert history[2]["content"] == "second"


def test_handle_uses_provider_selector_when_available() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    session_manager = SessionManager(session_store)

    manifest = load_provider_manifest("src/thoth/providers/mock/manifest.json")
    provider = MockProvider()
    provider.initialize({"mode": "test"})

    registry = ProviderRegistry()
    registry.register(provider_id="mock", provider=provider, manifest=manifest)
    selector = ProviderSelector(registry)

    orchestrator = RuntimeOrchestrator(
        session_manager=session_manager,
        event_bus=event_bus,
        provider_selector=selector,
    )

    response = orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_provider",
            gateway="cli",
            session={"session_id": "sess_provider"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="hello provider")],
        )
    )

    assert response.status is RuntimeStatus.SUCCESS
    assert response.messages[0].content == "[mock] echo: hello provider"


def test_handle_passes_session_history_to_provider() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    session_manager = SessionManager(session_store)

    provider = CapturingProvider()
    provider.initialize({"mode": "test"})
    manifest = ProviderManifest(
        schema_version="v1",
        type="provider",
        name="capturing",
        version="0.1.0",
        entrypoint="x:y",
        capabilities={"chat_completion": True},
        compatibility={},
        metadata={},
    )
    registry = ProviderRegistry()
    registry.register(provider_id="capturing", provider=provider, manifest=manifest)
    selector = ProviderSelector(registry)

    orchestrator = RuntimeOrchestrator(
        session_manager=session_manager,
        event_bus=event_bus,
        provider_selector=selector,
    )

    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_hist_1",
            gateway="cli",
            session={"session_id": "sess_hist_provider"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="primeira")],
        )
    )
    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_hist_2",
            gateway="cli",
            session={"session_id": "sess_hist_provider"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="segunda")],
        )
    )

    assert len(provider.seen_requests) == 2
    second_request = provider.seen_requests[1]
    contents = [message.content for message in second_request.messages]
    assert "primeira" in contents
    assert "segunda" in contents
