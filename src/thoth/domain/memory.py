"""Domain contracts for incremental learning memory pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryDecision(StrEnum):
    """Canonical memory decision outcomes."""

    PERSIST = "persist"
    DISCARD = "discard"
    REVIEW = "review"


@dataclass(slots=True, frozen=True)
class MemoryCandidate:
    """Single extracted learning candidate from request context."""

    candidate_id: str
    request_id: str
    session_id: str
    source: str
    event_type: str
    content: str
    role: str
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "source": self.source,
            "event_type": self.event_type,
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True, frozen=True)
class MemoryScore:
    """Scoring output with numeric value and rationale."""

    value: float
    reason: str


@dataclass(slots=True, frozen=True)
class MemoryUpdate:
    """Final memory update decision after scoring and redaction."""

    candidate_id: str
    request_id: str
    session_id: str
    source: str
    event_type: str
    content: str
    score: float
    redaction_applied: bool
    decision: MemoryDecision
    reason: str
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, str | float | bool]:
        return {
            "candidate_id": self.candidate_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "source": self.source,
            "event_type": self.event_type,
            "content": self.content,
            "score": self.score,
            "redaction_applied": self.redaction_applied,
            "decision": self.decision.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass(slots=True, frozen=True)
class LearningTriggerState:
    """Per-session trigger counters for learning cadence."""

    turns_since_memory: int = 0
    iterations_since_skill_signal: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "turns_since_memory": self.turns_since_memory,
            "iterations_since_skill_signal": self.iterations_since_skill_signal,
        }
