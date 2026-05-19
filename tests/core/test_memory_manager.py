from thoth.core.learning_store import InMemoryLearningStore
from thoth.core.memory_manager import MemoryManager, MemoryManagerConfig
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.events import RuntimeEventType
from thoth.domain.session import SessionState


class StaticReviewer:
    def __init__(self, suggestions: list[str]) -> None:
        self._suggestions = suggestions

    def review(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[str]:
        _ = request_id, session_id, input_messages, assistant_message
        return list(self._suggestions)


class FailingReviewer:
    def review(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[str]:
        _ = request_id, session_id, input_messages, assistant_message
        raise RuntimeError("boom")


def test_memory_manager_uses_global_learning_store_across_sessions() -> None:
    store = InMemoryLearningStore(max_updates=100)
    manager = MemoryManager(
        MemoryManagerConfig(enabled=True, max_updates=200),
        learning_store=store,
    )

    first_state = SessionState.create("sess_1")
    first_result = manager.apply(
        state=first_state,
        request_id="req_1",
        input_messages=[
            RuntimeMessage(role=RuntimeMessageRole.USER, content="prefiro respostas objetivas")
        ],
        assistant_message="ok",
    )

    second_state = SessionState.create("sess_2")
    second_result = manager.apply(
        state=second_state,
        request_id="req_2",
        input_messages=[
            RuntimeMessage(role=RuntimeMessageRole.USER, content="prefiro respostas objetivas")
        ],
        assistant_message="ok",
    )

    assert first_result.memory_updates
    assert second_result.memory_updates
    assert any("repeated_signal" in item["reason"] for item in second_result.memory_updates)


def test_memory_manager_includes_llm_review_suggestions_when_enabled() -> None:
    manager = MemoryManager(
        MemoryManagerConfig(enabled=True, review_enabled=True, max_review_suggestions=2),
        reviewer=StaticReviewer(
            [
                "Usuario prefere respostas objetivas",
                "Usuario prioriza padronizacao rigorosa",
            ]
        ),
    )

    state = SessionState.create("sess_review")
    result = manager.apply(
        state=state,
        request_id="req_review",
        input_messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="ok")],
        assistant_message="ok",
    )

    assert any(item["source"] == "learning_reviewer" for item in result.memory_updates)
    event_types = [item.type for item in result.events]
    assert RuntimeEventType.LEARNING_REVIEW_STARTED in event_types
    assert RuntimeEventType.LEARNING_REVIEW_COMPLETED in event_types


def test_memory_manager_handles_reviewer_failure_without_breaking() -> None:
    manager = MemoryManager(
        MemoryManagerConfig(enabled=True, review_enabled=True),
        reviewer=FailingReviewer(),
    )

    state = SessionState.create("sess_review_fail")
    result = manager.apply(
        state=state,
        request_id="req_review_fail",
        input_messages=[RuntimeMessage(role=RuntimeMessageRole.USER, content="ok")],
        assistant_message="ok",
    )

    event_types = [item.type for item in result.events]
    assert RuntimeEventType.LEARNING_REVIEW_STARTED in event_types
    assert RuntimeEventType.LEARNING_REVIEW_FAILED in event_types


def test_memory_manager_deduplicates_equivalent_updates_in_same_turn() -> None:
    manager = MemoryManager(
        MemoryManagerConfig(enabled=True, review_enabled=True, max_review_suggestions=3),
        reviewer=StaticReviewer(["prefiro respostas curtas em bullets"]),
    )

    state = SessionState.create("sess_dedupe")
    result = manager.apply(
        state=state,
        request_id="req_dedupe",
        input_messages=[
            RuntimeMessage(
                role=RuntimeMessageRole.USER,
                content="prefiro respostas curtas em bullets",
            )
        ],
        assistant_message="[mock] echo: prefiro respostas curtas em bullets",
    )

    normalized = {
        " ".join(str(item["content"]).strip().lower().replace("[mock] echo:", "").split())
        for item in result.memory_updates
    }
    assert len(normalized) == len(result.memory_updates)


def test_memory_manager_builds_runtime_context_from_global_learning() -> None:
    store = InMemoryLearningStore(max_updates=50)
    store.append(
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
            },
            {
                "candidate_id": "c2",
                "request_id": "r2",
                "session_id": "s2",
                "source": "input",
                "event_type": "turn.input",
                "content": "como eu prefiro minhas respostas?",
                "score": 0.7,
                "redaction_applied": False,
                "decision": "persist",
                "reason": "preference_signal",
                "timestamp": "t",
            },
        ]
    )

    manager = MemoryManager(MemoryManagerConfig(enabled=True), learning_store=store)
    context = manager.build_runtime_memory_context(state=SessionState.create("sess_ctx"))

    assert "prefiro respostas curtas em bullets" in context
    assert "como eu prefiro minhas respostas?" not in context


def test_memory_manager_does_not_persist_discard_updates_in_session_data() -> None:
    manager = MemoryManager(MemoryManagerConfig(enabled=True))

    state = SessionState.create("sess_discard_only")
    result = manager.apply(
        state=state,
        request_id="req_discard_only",
        input_messages=[
            RuntimeMessage(role=RuntimeMessageRole.USER, content="como eu prefiro minhas respostas?")
        ],
        assistant_message="- Voce prefere respostas curtas em bullets.",
    )

    assert result.memory_updates == []
    assert result.state.data.get("memory_updates") == []
    assert result.state.data["memory_meta"]["total_discarded"] >= 1
