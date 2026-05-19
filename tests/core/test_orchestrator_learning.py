from thoth.core.event_bus import InMemoryEventBus
from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelector
from thoth.core.memory_manager import MemoryManager, MemoryManagerConfig
from thoth.core.orchestrator import RuntimeOrchestrator
from thoth.core.session_manager import SessionManager
from thoth.core.learning_store import InMemoryLearningStore
from thoth.core.session_store import InMemorySessionStore
from thoth.domain.envelopes import RuntimeInputEnvelope, RuntimeMessage, RuntimeMessageRole
from thoth.domain.events import RuntimeEventType
from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import ProviderChunk, ProviderHealth, ProviderRequest, ProviderResponse


class CapturingProvider:
    def __init__(self) -> None:
        self._initialized = False
        self.seen_requests: list[ProviderRequest] = []

    def initialize(self, context: dict[str, object]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self.seen_requests.append(request)
        return ProviderResponse(request_id=request.request_id, output_text="ok")

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        self.seen_requests.append(request)
        return [ProviderChunk(request_id=request.request_id, index=0, content_delta="ok", done=True)]

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized)


def test_orchestrator_populates_memory_updates_when_learning_enabled() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    orchestrator = RuntimeOrchestrator(
        session_manager=SessionManager(session_store),
        event_bus=event_bus,
        memory_manager=MemoryManager(MemoryManagerConfig(enabled=True, max_updates=50)),
    )

    response = orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_learning",
            gateway="cli",
            session={"session_id": "sess_learning"},
            input=[
                RuntimeMessage(
                    role=RuntimeMessageRole.USER,
                    content="prefiro respostas curtas e padronizadas",
                )
            ],
        )
    )

    assert response.memory_updates
    session = session_store.get("sess_learning")
    assert session is not None
    assert "memory_updates" in session.data
    event_types = [event.type for event in event_bus.published_events]
    assert RuntimeEventType.MEMORY_CANDIDATE_CAPTURED in event_types


def test_orchestrator_injects_global_learning_context_into_provider_messages() -> None:
    event_bus = InMemoryEventBus()
    session_store = InMemorySessionStore()
    learning_store = InMemoryLearningStore(max_updates=50)
    learning_store.append(
        [
            {
                "candidate_id": "c1",
                "request_id": "r1",
                "session_id": "s1",
                "source": "input",
                "event_type": "turn.input",
                "content": "prefiro respostas curtas em bullets",
                "score": 0.8,
                "redaction_applied": False,
                "decision": "persist",
                "reason": "preference_signal",
                "timestamp": "t",
            }
        ]
    )

    provider = CapturingProvider()
    provider.initialize({"mode": "test"})
    registry = ProviderRegistry()
    registry.register(
        provider_id="capturing",
        provider=provider,
        manifest=ProviderManifest(
            schema_version="v1",
            type="provider",
            name="capturing",
            version="0.1.0",
            entrypoint="x:y",
            capabilities={"chat_completion": True},
            compatibility={},
            metadata={},
        ),
    )

    orchestrator = RuntimeOrchestrator(
        session_manager=SessionManager(session_store),
        event_bus=event_bus,
        provider_selector=ProviderSelector(registry),
        memory_manager=MemoryManager(
            MemoryManagerConfig(enabled=True),
            learning_store=learning_store,
        ),
    )

    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_ctx",
            gateway="cli",
            session={"session_id": "sess_ctx"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="como eu prefiro minhas respostas?")],
        )
    )

    assert provider.seen_requests
    first_message = provider.seen_requests[-1].messages[0]
    assert first_message.role is RuntimeMessageRole.SYSTEM
    assert "prefiro respostas curtas em bullets" in first_message.content
