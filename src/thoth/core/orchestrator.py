"""Minimal runtime orchestrator for layer 1 flow."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from thoth.core.context_builder import ProviderContextBuilder
from thoth.core.event_bus import EventBus
from thoth.core.memory_manager import MemoryManager
from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.core.session_compactor import SessionCompactor
from thoth.core.session_manager import SessionManager
from thoth.domain.envelopes import (
    RuntimeInputEnvelope,
    RuntimeMessage,
    RuntimeMessageRole,
    RuntimeOutputEnvelope,
    RuntimeStatus,
    validate_input_envelope,
    validate_output_envelope,
)
from thoth.domain.events import RuntimeEvent, RuntimeEventType
from thoth.domain.providers import ProviderRequest
from thoth.domain.session import SessionState


class RuntimeOrchestrator:
    """Coordinates input validation, session state and event emission."""

    _MESSAGE_HISTORY_LIMIT = 100
    def __init__(
        self,
        *,
        session_manager: SessionManager,
        event_bus: EventBus,
        provider_selector: ProviderSelector | None = None,
        provider_selection: ProviderSelectionConfig | None = None,
        session_compactor: SessionCompactor | None = None,
        context_builder: ProviderContextBuilder | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._event_bus = event_bus
        self._provider_selector = provider_selector
        self._provider_selection = provider_selection or ProviderSelectionConfig()
        self._session_compactor = session_compactor or SessionCompactor()
        self._context_builder = context_builder or ProviderContextBuilder()
        self._memory_manager = memory_manager or MemoryManager()

    def handle(self, envelope: RuntimeInputEnvelope) -> RuntimeOutputEnvelope:
        validate_input_envelope(envelope)

        session_id = self._resolve_session_id(envelope)
        self._event_bus.publish(
            RuntimeEvent(
                type=RuntimeEventType.REQUEST_RECEIVED,
                request_id=envelope.request_id,
                session_id=session_id,
                payload={"gateway": envelope.gateway},
            )
        )

        session_state = self._session_manager.get_or_create(
            session_id,
            metadata={"gateway": envelope.gateway},
        )
        assistant_message = self._resolve_assistant_message(envelope, session_state)
        message_history = self._build_message_history(
            existing_history=session_state.data.get("message_history"),
            request_id=envelope.request_id,
            input_messages=envelope.input,
            assistant_message=assistant_message,
        )
        updated_state = session_state.with_data(
            {
                "last_request_id": envelope.request_id,
                "last_gateway": envelope.gateway,
                "message_history": message_history,
            }
        )
        persisted_state = self._session_manager.persist(updated_state)

        compaction_plan = self._session_compactor.plan(state=persisted_state)
        if compaction_plan.started_event_payload is not None:
            self._event_bus.publish(
                RuntimeEvent(
                    type=RuntimeEventType.SESSION_COMPACTION_STARTED,
                    request_id=envelope.request_id,
                    session_id=persisted_state.session_id,
                    payload=compaction_plan.started_event_payload,
                )
            )

        compaction_result = self._session_compactor.compact_if_needed(
            state=persisted_state,
            request_id=envelope.request_id,
            plan=compaction_plan,
        )
        if compaction_result.compacted:
            persisted_state = self._session_manager.persist(compaction_result.state)
            payload = dict(compaction_result.completed_event_payload or {})
            payload["session_revision"] = persisted_state.revision
            self._event_bus.publish(
                RuntimeEvent(
                    type=RuntimeEventType.SESSION_COMPACTED,
                    request_id=envelope.request_id,
                    session_id=persisted_state.session_id,
                    payload=payload,
                )
            )

        memory_result = self._memory_manager.apply(
            state=persisted_state,
            request_id=envelope.request_id,
            input_messages=envelope.input,
            assistant_message=assistant_message,
        )
        if memory_result.state.revision != persisted_state.revision:
            persisted_state = self._session_manager.persist(memory_result.state)

        for item in memory_result.events:
            self._event_bus.publish(
                RuntimeEvent(
                    type=item.type,
                    request_id=envelope.request_id,
                    session_id=persisted_state.session_id,
                    payload=item.payload,
                )
            )

        audit_ref = f"session:{persisted_state.session_id}:rev:{persisted_state.revision}"
        if compaction_result.compacted:
            audit_ref = f"{audit_ref}:compacted:{compaction_result.compacted_messages}"

        response = RuntimeOutputEnvelope(
            request_id=envelope.request_id,
            status=RuntimeStatus.SUCCESS,
            messages=[
                RuntimeMessage(
                    role=RuntimeMessageRole.ASSISTANT,
                    content=assistant_message,
                )
            ],
            memory_updates=memory_result.memory_updates,
            audit_ref=audit_ref,
        )
        validate_output_envelope(response)

        self._event_bus.publish(
            RuntimeEvent(
                type=RuntimeEventType.RESPONSE_EMITTED,
                request_id=envelope.request_id,
                session_id=persisted_state.session_id,
                payload={
                    "status": response.status.value,
                    "session_revision": persisted_state.revision,
                },
            )
        )
        return response

    def _resolve_assistant_message(
        self,
        envelope: RuntimeInputEnvelope,
        session_state: SessionState,
    ) -> str:
        session_id = session_state.session_id
        if self._provider_selector is None:
            return f"Request '{envelope.request_id}' processed for session '{session_id}'."

        provider_messages = self._context_builder.build(
            session_state=session_state,
            input_messages=envelope.input,
        )
        learning_context = self._memory_manager.build_runtime_memory_context(state=session_state)
        if learning_context:
            provider_messages = [
                RuntimeMessage(role=RuntimeMessageRole.SYSTEM, content=learning_context),
                *provider_messages,
            ]
        selected_provider = self._provider_selector.select(
            capability="chat_completion",
            config=self._provider_selection,
        )
        provider_request = ProviderRequest(
            request_id=envelope.request_id,
            messages=provider_messages,
            metadata={
                "gateway": envelope.gateway,
                "session_id": session_id,
                "provider_id": selected_provider.provider_id,
            },
        )
        provider_response = selected_provider.provider.execute(provider_request)
        return provider_response.output_text

    @staticmethod
    def _resolve_session_id(envelope: RuntimeInputEnvelope) -> str:
        raw_session_id = str(envelope.session.get("session_id", "")).strip()
        if raw_session_id:
            return raw_session_id
        return f"session:{envelope.request_id}"

    @classmethod
    def _build_message_history(
        cls,
        *,
        existing_history: Any,
        request_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        if isinstance(existing_history, list):
            for item in existing_history:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("role"), str)
                    and isinstance(item.get("content"), str)
                ):
                    history.append(
                        {
                            "request_id": str(item.get("request_id", "")),
                            "role": item["role"],
                            "content": item["content"],
                            "timestamp": str(item.get("timestamp", "")),
                        }
                    )

        timestamp = datetime.now(UTC).isoformat()
        for message in input_messages:
            history.append(
                {
                    "request_id": request_id,
                    "role": message.role.value,
                    "content": message.content,
                    "timestamp": timestamp,
                }
            )

        history.append(
            {
                "request_id": request_id,
                "role": RuntimeMessageRole.ASSISTANT.value,
                "content": assistant_message,
                "timestamp": timestamp,
            }
        )

        return history[-cls._MESSAGE_HISTORY_LIMIT :]
