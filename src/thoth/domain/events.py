"""Canonical runtime event models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class RuntimeEventType(StrEnum):
    """Minimal canonical event types for layer 1."""

    REQUEST_RECEIVED = "request.received"
    SESSION_COMPACTION_STARTED = "session.compaction.started"
    SESSION_COMPACTED = "session.compacted"
    MEMORY_CANDIDATE_CAPTURED = "memory.candidate.captured"
    MEMORY_UPDATE_PERSISTED = "memory.update.persisted"
    MEMORY_UPDATE_DISCARDED = "memory.update.discarded"
    MEMORY_UPDATE_REVIEW_REQUIRED = "memory.update.review_required"
    LEARNING_REVIEW_STARTED = "learning.review.started"
    LEARNING_REVIEW_COMPLETED = "learning.review.completed"
    LEARNING_REVIEW_FAILED = "learning.review.failed"
    RESPONSE_EMITTED = "response.emitted"


@dataclass(slots=True, frozen=True)
class RuntimeEvent:
    """Runtime domain event emitted by orchestrated operations."""

    type: RuntimeEventType
    request_id: str
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)
