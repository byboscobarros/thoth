"""Session memory manager integrating learning pipeline and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from thoth.core.learning_reviewer import LearningReviewerPort
from thoth.core.learning_store import LearningStore
from thoth.core.memory_pipeline import MemoryPipeline, MemoryPipelineConfig
from thoth.domain.envelopes import RuntimeMessage
from thoth.domain.events import RuntimeEventType
from thoth.domain.memory import MemoryDecision, MemoryUpdate
from thoth.domain.session import SessionState
from thoth.domain.session_compaction import summary_from_data


@dataclass(slots=True, frozen=True)
class MemoryManagerConfig:
    """Runtime memory learning manager controls."""

    enabled: bool = False
    persist_threshold: float = 0.70
    review_threshold: float = 0.50
    max_updates: int = 200
    max_candidates: int = 10
    review_enabled: bool = False
    max_review_suggestions: int = 3


@dataclass(slots=True, frozen=True)
class MemoryManagerEvent:
    """Event descriptor emitted by memory manager decisions."""

    type: RuntimeEventType
    payload: dict[str, Any]


@dataclass(slots=True, frozen=True)
class MemoryManagerResult:
    """Memory learning operation outcome."""

    state: SessionState
    memory_updates: list[dict[str, Any]]
    events: list[MemoryManagerEvent]


class MemoryManager:
    """Execute learning pipeline and persist updates in session state."""

    def __init__(
        self,
        config: MemoryManagerConfig | None = None,
        pipeline: MemoryPipeline | None = None,
        learning_store: LearningStore | None = None,
        reviewer: LearningReviewerPort | None = None,
    ) -> None:
        self._config = config or MemoryManagerConfig()
        self._learning_store = learning_store
        self._reviewer = reviewer
        self._pipeline = pipeline or MemoryPipeline(
            config=MemoryPipelineConfig(
                persist_threshold=self._config.persist_threshold,
                review_threshold=self._config.review_threshold,
                max_candidates=self._config.max_candidates,
            )
        )

    def apply(
        self,
        *,
        state: SessionState,
        request_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> MemoryManagerResult:
        if not self._config.enabled:
            return MemoryManagerResult(state=state, memory_updates=[], events=[])

        session_summary = summary_from_data(state.data).short
        existing_updates = [
            item
            for item in _normalize_updates(state.data.get("memory_updates"))
            if str(item.get("decision", "")) != MemoryDecision.DISCARD.value
        ]
        global_updates = self._learning_store.load() if self._learning_store is not None else []
        previously_persisted = {
            str(item.get("content", "")).strip().lower()
            for item in [*global_updates, *existing_updates]
            if str(item.get("decision", "")) == MemoryDecision.PERSIST.value
            and str(item.get("content", "")).strip()
        }

        candidates, updates = self._pipeline.process(
            request_id=request_id,
            session_id=state.session_id,
            input_messages=input_messages,
            assistant_message=assistant_message,
            session_summary=session_summary,
            previously_persisted_contents=previously_persisted,
        )

        update_dicts = [update.to_dict() for update in updates]

        events: list[MemoryManagerEvent] = []
        review_suggestions: list[str] = []
        if self._config.review_enabled and self._reviewer is not None:
            events.append(
                MemoryManagerEvent(
                    type=RuntimeEventType.LEARNING_REVIEW_STARTED,
                    payload={"trigger": "end_turn"},
                )
            )
            try:
                review_suggestions = self._reviewer.review(
                    request_id=request_id,
                    session_id=state.session_id,
                    input_messages=input_messages,
                    assistant_message=assistant_message,
                )
                events.append(
                    MemoryManagerEvent(
                        type=RuntimeEventType.LEARNING_REVIEW_COMPLETED,
                        payload={"suggestions": len(review_suggestions)},
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive runtime guard.
                events.append(
                    MemoryManagerEvent(
                        type=RuntimeEventType.LEARNING_REVIEW_FAILED,
                        payload={"reason": type(exc).__name__},
                    )
                )
                review_suggestions = []

        review_update_dicts = self._review_updates_from_suggestions(
            suggestions=review_suggestions,
            request_id=request_id,
            session_id=state.session_id,
            existing_persisted=previously_persisted,
            max_items=self._config.max_review_suggestions,
        )
        update_dicts.extend(review_update_dicts)
        update_dicts = _deduplicate_updates(update_dicts)

        retained_updates = [
            item for item in update_dicts if item.get("decision") != MemoryDecision.DISCARD.value
        ]

        if self._learning_store is not None:
            persisted_updates = [
                item for item in update_dicts if item.get("decision") == MemoryDecision.PERSIST.value
            ]
            if persisted_updates:
                self._learning_store.append(persisted_updates)

        merged_updates = [*existing_updates, *retained_updates]
        if self._config.max_updates > 0:
            merged_updates = merged_updates[-self._config.max_updates :]

        persisted_count = sum(1 for item in update_dicts if item["decision"] == MemoryDecision.PERSIST)
        discarded_count = sum(1 for item in update_dicts if item["decision"] == MemoryDecision.DISCARD)
        review_count = sum(1 for item in update_dicts if item["decision"] == MemoryDecision.REVIEW)

        previous_meta = state.data.get("memory_meta", {})
        total_persisted = int(previous_meta.get("total_persisted", 0)) + persisted_count
        total_discarded = int(previous_meta.get("total_discarded", 0)) + discarded_count
        total_review = int(previous_meta.get("total_review", 0)) + review_count

        new_state = state.with_data(
            {
                "memory_updates": merged_updates,
                "memory_meta": {
                    "total_persisted": total_persisted,
                    "total_discarded": total_discarded,
                    "total_review": total_review,
                    "last_update_at": datetime.now(UTC).isoformat(),
                },
            }
        )

        for candidate in candidates:
            events.append(
                MemoryManagerEvent(
                    type=RuntimeEventType.MEMORY_CANDIDATE_CAPTURED,
                    payload={
                        "candidate_id": candidate.candidate_id,
                        "source": candidate.source,
                        "event_type": candidate.event_type,
                    },
                )
            )

        for update in update_dicts:
            event_type = RuntimeEventType.MEMORY_UPDATE_DISCARDED
            if update["decision"] == MemoryDecision.PERSIST:
                event_type = RuntimeEventType.MEMORY_UPDATE_PERSISTED
            elif update["decision"] == MemoryDecision.REVIEW:
                event_type = RuntimeEventType.MEMORY_UPDATE_REVIEW_REQUIRED

            events.append(
                MemoryManagerEvent(
                    type=event_type,
                    payload={
                        "candidate_id": update["candidate_id"],
                        "score": update["score"],
                        "decision": update["decision"],
                    },
                )
            )

        return MemoryManagerResult(
            state=new_state,
            memory_updates=retained_updates,
            events=events,
        )

    def build_runtime_memory_context(
        self,
        *,
        state: SessionState,
        max_items: int = 8,
    ) -> str:
        if not self._config.enabled or max_items <= 0:
            return ""

        session_updates = _normalize_updates(state.data.get("memory_updates"))
        global_updates = self._learning_store.load() if self._learning_store is not None else []

        memories: list[str] = []
        seen: set[str] = set()
        for item in [*global_updates, *session_updates]:
            if str(item.get("decision", "")) != MemoryDecision.PERSIST.value:
                continue
            content = str(item.get("content", "")).strip()
            canonical = _canonical_memory_content(content)
            if not canonical or canonical in seen:
                continue
            if _looks_like_question(canonical):
                continue
            seen.add(canonical)
            memories.append(content)

        if not memories:
            return ""

        selected = memories[-max_items:]
        lines = ["Memorias duraveis do usuario:"]
        lines.extend(f"- {item}" for item in selected)
        return "\n".join(lines)

    def _review_updates_from_suggestions(
        self,
        *,
        suggestions: list[str],
        request_id: str,
        session_id: str,
        existing_persisted: set[str],
        max_items: int,
    ) -> list[dict[str, Any]]:
        if max_items <= 0:
            return []

        updates: list[dict[str, Any]] = []
        seen = set(existing_persisted)
        for index, suggestion in enumerate(suggestions):
            if len(updates) >= max_items:
                break

            content = suggestion.strip()
            if not content:
                continue
            lowered = content.lower()
            if lowered in seen:
                continue
            seen.add(lowered)

            update = MemoryUpdate(
                candidate_id=f"{request_id}:review:{index}",
                request_id=request_id,
                session_id=session_id,
                source="learning_reviewer",
                event_type="learning.review",
                content=content,
                score=0.95,
                redaction_applied=False,
                decision=MemoryDecision.PERSIST,
                reason="llm_review:durable_signal",
            )
            updates.append(update.to_dict())
        return updates


def _normalize_updates(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def _deduplicate_updates(updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, update in enumerate(updates):
        key = _canonical_memory_content(str(update.get("content", "")))
        if not key:
            continue

        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = (index, update)
            continue

        _, incumbent = current
        if _is_better_update(update, incumbent):
            first_index = current[0]
            best_by_key[key] = (first_index, update)

    ordered = sorted(best_by_key.values(), key=lambda item: item[0])
    return [item[1] for item in ordered]


def _canonical_memory_content(content: str) -> str:
    cleaned = content.strip().lower()
    if cleaned.startswith("[mock] echo:"):
        cleaned = cleaned[len("[mock] echo:") :].strip()
    elif cleaned.startswith("echo:"):
        cleaned = cleaned[len("echo:") :].strip()
    return " ".join(cleaned.split())


def _is_better_update(candidate: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    candidate_rank = _update_rank(candidate)
    incumbent_rank = _update_rank(incumbent)
    if candidate_rank > incumbent_rank:
        return True
    if candidate_rank < incumbent_rank:
        return False

    candidate_score = float(candidate.get("score", 0.0))
    incumbent_score = float(incumbent.get("score", 0.0))
    if candidate_score > incumbent_score:
        return True
    if candidate_score < incumbent_score:
        return False

    return _source_priority(str(candidate.get("source", ""))) > _source_priority(
        str(incumbent.get("source", ""))
    )


def _update_rank(update: dict[str, Any]) -> int:
    decision = str(update.get("decision", ""))
    if decision == MemoryDecision.PERSIST.value:
        return 3
    if decision == MemoryDecision.REVIEW.value:
        return 2
    if decision == MemoryDecision.DISCARD.value:
        return 1
    return 0


def _source_priority(source: str) -> int:
    if source == "learning_reviewer":
        return 4
    if source == "input":
        return 3
    if source == "session_summary":
        return 2
    if source == "assistant":
        return 1
    return 0


def _looks_like_question(content: str) -> bool:
    compact = " ".join(content.split())
    if not compact:
        return False
    if "?" not in compact:
        return False
    return compact.startswith(("como", "qual", "quais", "o que", "por que", "pq", "quando", "onde"))
