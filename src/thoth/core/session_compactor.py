"""Session compaction service with pluggable summarization strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from thoth.core.session_summarizer import HeuristicSessionSummarizer, SessionSummarizer
from thoth.domain.session import SessionState
from thoth.domain.session_compaction import (
    CompactionMeta,
    compaction_meta_from_data,
    summary_from_data,
)


@dataclass(slots=True, frozen=True)
class SessionCompactionConfig:
    """Configuration for session compaction thresholds and summary limits."""

    active_window: int = 40
    compaction_threshold: int = 20
    max_summary_chars: int = 1200
    context_token_limit: int | None = None
    compaction_token_threshold_ratio: float = 0.50


@dataclass(slots=True, frozen=True)
class SessionCompactionResult:
    """Outcome of a compaction attempt."""

    state: SessionState
    compacted: bool
    messages_before: int
    messages_after: int
    compacted_messages: int
    completed_event_payload: dict[str, int] | None = None


@dataclass(slots=True, frozen=True)
class SessionCompactionPlan:
    """Pre-computed compaction decision and start event semantics."""

    should_compact: bool
    messages_before: int
    messages_compactable: int

    @property
    def started_event_payload(self) -> dict[str, int] | None:
        if not self.should_compact:
            return None
        return {
            "messages_before": self.messages_before,
            "messages_compactable": self.messages_compactable,
        }


class SessionCompactor:
    """Compacts message history and persists a structured summary."""

    def __init__(
        self,
        config: SessionCompactionConfig | None = None,
        summarizer: SessionSummarizer | None = None,
    ) -> None:
        self._config = config or SessionCompactionConfig()
        self._summarizer = summarizer or HeuristicSessionSummarizer()

    def plan(self, *, state: SessionState) -> SessionCompactionPlan:
        """Build compaction plan and start event payload details."""

        history = _normalize_history(state.data.get("message_history"))
        compactable_count = self._compactable_count(history_size=len(history))
        compactable_available = compactable_count > 0

        should_compact_by_messages = compactable_count >= self._config.compaction_threshold
        should_compact_by_tokens = False
        if compactable_available:
            token_threshold = self._token_compaction_threshold()
            if token_threshold is not None:
                estimated_tokens = _estimate_history_tokens(history)
                should_compact_by_tokens = estimated_tokens >= token_threshold

        return SessionCompactionPlan(
            should_compact=should_compact_by_messages or should_compact_by_tokens,
            messages_before=len(history),
            messages_compactable=compactable_count,
        )

    def compact_if_needed(
        self,
        *,
        state: SessionState,
        request_id: str,
        plan: SessionCompactionPlan | None = None,
    ) -> SessionCompactionResult:
        history = _normalize_history(state.data.get("message_history"))
        before_count = len(history)

        effective_plan = plan or self.plan(state=state)

        compactable_count = effective_plan.messages_compactable
        compactable = history[:compactable_count] if compactable_count > 0 else []
        if not effective_plan.should_compact:
            return SessionCompactionResult(
                state=state,
                compacted=False,
                messages_before=before_count,
                messages_after=before_count,
                compacted_messages=0,
                completed_event_payload=None,
            )

        active_history = history[-self._config.active_window :]
        previous_summary = summary_from_data(state.data)
        previous_meta = compaction_meta_from_data(state.data)

        merged_summary = self._summarizer.summarize(
            previous_summary=previous_summary,
            compacted_history=compactable,
            max_summary_chars=self._config.max_summary_chars,
        )
        updated_meta = CompactionMeta(
            total_messages_seen=before_count,
            total_messages_compacted=previous_meta.total_messages_compacted + len(compactable),
            last_compaction_at=datetime.now(UTC).isoformat(),
            last_compacted_request_id=request_id,
        )

        new_state = state.with_data(
            {
                "message_history": active_history,
                "session_summary": merged_summary.to_dict(),
                "compaction_meta": updated_meta.to_dict(),
            }
        )
        return SessionCompactionResult(
            state=new_state,
            compacted=True,
            messages_before=before_count,
            messages_after=len(active_history),
            compacted_messages=len(compactable),
            completed_event_payload={
                "messages_before": before_count,
                "messages_after": len(active_history),
                "messages_compacted": len(compactable),
            },
        )

    def _compactable_count(self, *, history_size: int) -> int:
        if history_size <= self._config.active_window:
            return 0
        return history_size - self._config.active_window

    def _token_compaction_threshold(self) -> int | None:
        context_limit = self._config.context_token_limit
        if context_limit is None or context_limit <= 0:
            return None

        ratio = self._config.compaction_token_threshold_ratio
        if ratio <= 0:
            return None

        threshold = int(context_limit * ratio)
        if threshold <= 0:
            return None
        return threshold


def _normalize_history(raw_history: Any) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not isinstance(raw_history, list):
        return normalized

    for item in raw_history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        normalized.append(
            {
                "request_id": str(item.get("request_id", "")),
                "role": role,
                "content": content,
                "timestamp": str(item.get("timestamp", "")),
            }
        )
    return normalized


def _estimate_history_tokens(history: list[dict[str, str]]) -> int:
    estimated = 0
    for item in history:
        # Rough approximation for role/metadata framing + content payload.
        estimated += 6 + max(1, len(item["content"]) // 4)
    return estimated
