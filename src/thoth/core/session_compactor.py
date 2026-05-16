"""Session compaction service with deterministic heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from thoth.domain.session import SessionState
from thoth.domain.session_compaction import (
    CompactionMeta,
    SessionSummary,
    compaction_meta_from_data,
    summary_from_data,
)


@dataclass(slots=True, frozen=True)
class SessionCompactionConfig:
    """Configuration for session compaction thresholds and summary limits."""

    active_window: int = 40
    compaction_threshold: int = 20
    max_summary_chars: int = 1200


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

    def __init__(self, config: SessionCompactionConfig | None = None) -> None:
        self._config = config or SessionCompactionConfig()

    def plan(self, *, state: SessionState) -> SessionCompactionPlan:
        """Build compaction plan and start event payload details."""

        history = _normalize_history(state.data.get("message_history"))
        compactable_count = self._compactable_count(history_size=len(history))
        return SessionCompactionPlan(
            should_compact=compactable_count >= self._config.compaction_threshold,
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

        merged_summary = _merge_summary(
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


def _merge_summary(
    *,
    previous_summary: SessionSummary,
    compacted_history: list[dict[str, str]],
    max_summary_chars: int,
) -> SessionSummary:
    extracted = _extract_structured_signals(compacted_history)

    merged_structured: dict[str, list[str]] = {}
    for key in ["facts", "goals", "decisions", "open_tasks"]:
        merged_structured[key] = _merge_unique(
            previous_summary.structured.get(key, []),
            extracted.get(key, []),
        )

    short_summary = _build_short_summary(compacted_history, merged_structured, max_summary_chars)
    return SessionSummary(version=1, short=short_summary, structured=merged_structured)


def _extract_structured_signals(compacted_history: list[dict[str, str]]) -> dict[str, list[str]]:
    facts: list[str] = []
    goals: list[str] = []
    decisions: list[str] = []
    open_tasks: list[str] = []

    for item in compacted_history:
        role = item["role"].strip().lower()
        content = item["content"].strip()
        lowered = content.lower()

        if role == "user":
            if "?" in content or any(
                term in lowered for term in ["quero", "preciso", "como", "pode"]
            ):
                goals.append(content)
            else:
                facts.append(content)
            if any(
                term in lowered for term in ["falta", "pendente", "todo", "implemente", "fazer"]
            ):
                open_tasks.append(content)

        if role == "assistant" and any(
            term in lowered for term in ["feito", "implementado", "decid", "vamos seguir", "conclu"]
        ):
            decisions.append(content)

    return {
        "facts": facts[:8],
        "goals": goals[:8],
        "decisions": decisions[:8],
        "open_tasks": open_tasks[:8],
    }


def _build_short_summary(
    compacted_history: list[dict[str, str]],
    structured: dict[str, list[str]],
    max_summary_chars: int,
) -> str:
    snippets: list[str] = []

    if structured.get("goals"):
        snippets.append(f"Objetivos: {structured['goals'][0]}")
    if structured.get("facts"):
        snippets.append(f"Fatos: {structured['facts'][0]}")
    if structured.get("open_tasks"):
        snippets.append(f"Pendencias: {structured['open_tasks'][0]}")
    if structured.get("decisions"):
        snippets.append(f"Decisoes: {structured['decisions'][0]}")

    if not snippets:
        for item in compacted_history[-4:]:
            role = item["role"]
            content = item["content"].strip()
            if content:
                snippets.append(f"{role}: {content}")

    summary = " | ".join(snippets).strip()
    if len(summary) <= max_summary_chars:
        return summary
    return summary[: max_summary_chars - 3].rstrip() + "..."


def _merge_unique(current: list[str], new_items: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for item in [*current, *new_items]:
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        merged.append(candidate)
    return merged[:20]
