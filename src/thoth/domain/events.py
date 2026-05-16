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
    RESPONSE_EMITTED = "response.emitted"


@dataclass(slots=True, frozen=True)
class RuntimeEvent:
    """Runtime domain event emitted by orchestrated operations."""

    type: RuntimeEventType
    request_id: str
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)
