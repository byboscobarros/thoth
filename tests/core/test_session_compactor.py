from datetime import UTC, datetime

from thoth.core.session_compactor import SessionCompactionConfig, SessionCompactor
from thoth.domain.session import SessionState
from thoth.domain.session_compaction import SessionSummary


class FixedSummarizer:
    def summarize(
        self,
        *,
        previous_summary: SessionSummary,
        compacted_history: list[dict[str, str]],
        max_summary_chars: int,
    ) -> SessionSummary:
        _ = previous_summary, compacted_history, max_summary_chars
        return SessionSummary(
            version=1,
            short="fixed-summary",
            structured={
                "facts": ["fixed-fact"],
                "goals": [],
                "decisions": [],
                "open_tasks": [],
            },
        )


def _history(size: int) -> list[dict[str, str]]:
    now = datetime.now(UTC).isoformat()
    items: list[dict[str, str]] = []
    for index in range(size):
        role = "user" if index % 2 == 0 else "assistant"
        items.append(
            {
                "request_id": f"req_{index}",
                "role": role,
                "content": f"mensagem {index}",
                "timestamp": now,
            }
        )
    return items


def test_compactor_compacts_when_threshold_is_reached() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=4,
            compaction_threshold=3,
            max_summary_chars=300,
        )
    )
    state = SessionState.create("sess_1", data={"message_history": _history(10)})

    result = compactor.compact_if_needed(state=state, request_id="req_10")

    assert result.compacted is True
    assert result.messages_before == 10
    assert result.messages_after == 4
    assert result.compacted_messages == 6
    assert len(result.state.data["message_history"]) == 4
    assert result.state.data["session_summary"]["short"]
    assert result.state.data["compaction_meta"]["last_compacted_request_id"] == "req_10"
    assert result.completed_event_payload is not None
    assert result.completed_event_payload["messages_compacted"] == 6


def test_compactor_does_not_compact_below_threshold() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=8,
            compaction_threshold=5,
            max_summary_chars=300,
        )
    )
    state = SessionState.create("sess_2", data={"message_history": _history(10)})

    result = compactor.compact_if_needed(state=state, request_id="req_10")

    assert result.compacted is False
    assert result.messages_before == 10
    assert result.messages_after == 10
    assert result.compacted_messages == 0
    assert result.completed_event_payload is None


def test_compactor_accumulates_compaction_meta() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=4,
            compaction_threshold=2,
            max_summary_chars=300,
        )
    )
    state = SessionState.create(
        "sess_3",
        data={
            "message_history": _history(12),
            "compaction_meta": {
                "total_messages_seen": 20,
                "total_messages_compacted": 10,
                "last_compaction_at": "2026-05-14T00:00:00+00:00",
                "last_compacted_request_id": "req_old",
            },
            "session_summary": {
                "version": 1,
                "short": "resumo anterior",
                "structured": {
                    "facts": ["f1"],
                    "goals": [],
                    "decisions": [],
                    "open_tasks": [],
                },
            },
        },
    )

    result = compactor.compact_if_needed(state=state, request_id="req_new")

    assert result.compacted is True
    meta = result.state.data["compaction_meta"]
    assert meta["total_messages_seen"] == 12
    assert meta["total_messages_compacted"] == 18
    assert meta["last_compacted_request_id"] == "req_new"


def test_compactor_plan_reports_start_event_payload() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=4,
            compaction_threshold=2,
            max_summary_chars=300,
        )
    )
    state = SessionState.create("sess_plan", data={"message_history": _history(10)})

    plan = compactor.plan(state=state)

    assert plan.should_compact is True
    assert plan.messages_before == 10
    assert plan.messages_compactable == 6
    assert plan.started_event_payload == {
        "messages_before": 10,
        "messages_compactable": 6,
    }


def test_compactor_uses_injected_summarizer() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=4,
            compaction_threshold=2,
            max_summary_chars=300,
        ),
        summarizer=FixedSummarizer(),
    )
    state = SessionState.create("sess_custom", data={"message_history": _history(10)})

    result = compactor.compact_if_needed(state=state, request_id="req_custom")

    assert result.compacted is True
    assert result.state.data["session_summary"]["short"] == "fixed-summary"
    assert result.state.data["session_summary"]["structured"]["facts"] == ["fixed-fact"]


def test_compactor_can_trigger_by_estimated_tokens() -> None:
    compactor = SessionCompactor(
        config=SessionCompactionConfig(
            active_window=4,
            compaction_threshold=100,
            max_summary_chars=300,
            context_token_limit=80,
            compaction_token_threshold_ratio=0.5,
        )
    )
    state = SessionState.create(
        "sess_token_threshold",
        data={
            "message_history": [
                {
                    "request_id": "r1",
                    "role": "user",
                    "content": "x" * 120,
                    "timestamp": "t",
                },
                {
                    "request_id": "r1",
                    "role": "assistant",
                    "content": "y" * 120,
                    "timestamp": "t",
                },
                {
                    "request_id": "r2",
                    "role": "user",
                    "content": "z" * 120,
                    "timestamp": "t",
                },
                {
                    "request_id": "r2",
                    "role": "assistant",
                    "content": "w" * 120,
                    "timestamp": "t",
                },
                {
                    "request_id": "r3",
                    "role": "user",
                    "content": "k" * 120,
                    "timestamp": "t",
                },
                {
                    "request_id": "r3",
                    "role": "assistant",
                    "content": "m" * 120,
                    "timestamp": "t",
                },
            ]
        },
    )

    plan = compactor.plan(state=state)

    assert plan.should_compact is True
    assert plan.messages_compactable == 2
