from thoth.core.context_builder import ProviderContextBuilder, ProviderContextConfig
from thoth.core.event_bus import InMemoryEventBus
from thoth.core.orchestrator import RuntimeOrchestrator
from thoth.core.provider_registry import ProviderRegistry
from thoth.core.provider_selector import ProviderSelector
from thoth.core.session_compactor import SessionCompactionConfig, SessionCompactor
from thoth.core.session_manager import SessionManager
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
        return [
            ProviderChunk(
                request_id=request.request_id,
                index=0,
                content_delta="ok",
                done=True,
            )
        ]

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized)


def _build_orchestrator(
    provider: CapturingProvider,
) -> tuple[RuntimeOrchestrator, InMemorySessionStore, InMemoryEventBus]:
    event_bus = InMemoryEventBus()
    store = InMemorySessionStore()
    session_manager = SessionManager(store)

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
        session_manager=session_manager,
        event_bus=event_bus,
        provider_selector=ProviderSelector(registry),
        session_compactor=SessionCompactor(
            config=SessionCompactionConfig(
                active_window=4,
                compaction_threshold=2,
                max_summary_chars=500,
            )
        ),
        context_builder=ProviderContextBuilder(
            config=ProviderContextConfig(provider_context_limit=6, max_summary_chars=500)
        ),
    )
    return orchestrator, store, event_bus


def test_orchestrator_compacts_session_and_emits_event() -> None:
    provider = CapturingProvider()
    provider.initialize({"mode": "test"})
    orchestrator, store, event_bus = _build_orchestrator(provider)

    for index in range(3):
        orchestrator.handle(
            RuntimeInputEnvelope(
                request_id=f"req_{index}",
                gateway="cli",
                session={"session_id": "sess_compact"},
                input=[RuntimeMessage(role=RuntimeMessageRole.USER, content=f"mensagem {index}")],
            )
        )

    events = [event.type for event in event_bus.published_events]
    assert RuntimeEventType.SESSION_COMPACTION_STARTED in events
    assert RuntimeEventType.SESSION_COMPACTED in events

    started_index = events.index(RuntimeEventType.SESSION_COMPACTION_STARTED)
    compacted_index = events.index(RuntimeEventType.SESSION_COMPACTED)
    assert started_index < compacted_index

    session = store.get("sess_compact")
    assert session is not None
    assert "session_summary" in session.data
    assert "compaction_meta" in session.data
    assert len(session.data["message_history"]) <= 4


def test_orchestrator_rehydrates_provider_context_with_summary() -> None:
    provider = CapturingProvider()
    provider.initialize({"mode": "test"})
    orchestrator, store, _ = _build_orchestrator(provider)

    for index in range(3):
        orchestrator.handle(
            RuntimeInputEnvelope(
                request_id=f"req_a_{index}",
                gateway="cli",
                session={"session_id": "sess_context"},
                input=[RuntimeMessage(role=RuntimeMessageRole.USER, content=f"pergunta {index}?")],
            )
        )

    orchestrator.handle(
        RuntimeInputEnvelope(
            request_id="req_a_3",
            gateway="cli",
            session={"session_id": "sess_context"},
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content="nova pergunta")],
        )
    )

    assert provider.seen_requests
    final_request = provider.seen_requests[-1]
    assert final_request.messages[0].role is RuntimeMessageRole.SYSTEM
    assert "Resumo da sessao" in final_request.messages[0].content
    assert final_request.messages[-1].content == "nova pergunta"

    session = store.get("sess_context")
    assert session is not None
    assert session.data["compaction_meta"]["total_messages_compacted"] >= 2
