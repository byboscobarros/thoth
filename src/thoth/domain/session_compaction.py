"""Session compaction domain models for canonical runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True, frozen=True)
class SessionSummary:
    """Persisted summary of compacted session context."""

    version: int = 1
    short: str = ""
    structured: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: dict[str, list[str]] = {
            "facts": [],
            "goals": [],
            "decisions": [],
            "open_tasks": [],
        }
        for key in normalized:
            raw_items = self.structured.get(key, [])
            if not isinstance(raw_items, list):
                continue
            seen: set[str] = set()
            collected: list[str] = []
            for item in raw_items:
                if not isinstance(item, str):
                    continue
                candidate = item.strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                collected.append(candidate)
            normalized[key] = collected

        object.__setattr__(self, "structured", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "short": self.short,
            "structured": {key: list(value) for key, value in self.structured.items()},
        }


@dataclass(slots=True, frozen=True)
class CompactionMeta:
    """Operational metadata that tracks compaction evolution."""

    total_messages_seen: int = 0
    total_messages_compacted: int = 0
    last_compaction_at: str | None = None
    last_compacted_request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_messages_seen": self.total_messages_seen,
            "total_messages_compacted": self.total_messages_compacted,
            "last_compaction_at": self.last_compaction_at,
            "last_compacted_request_id": self.last_compacted_request_id,
        }


def summary_from_data(data: dict[str, Any]) -> SessionSummary:
    payload = data.get("session_summary")
    if not isinstance(payload, dict):
        return SessionSummary()

    version = payload.get("version")
    short = payload.get("short")
    structured = payload.get("structured")

    return SessionSummary(
        version=version if isinstance(version, int) and version > 0 else 1,
        short=short if isinstance(short, str) else "",
        structured=structured if isinstance(structured, dict) else {},
    )


def compaction_meta_from_data(data: dict[str, Any]) -> CompactionMeta:
    payload = data.get("compaction_meta")
    if not isinstance(payload, dict):
        return CompactionMeta(last_compaction_at=_utc_now_iso())

    total_messages_seen = payload.get("total_messages_seen")
    total_messages_compacted = payload.get("total_messages_compacted")
    last_compaction_at = payload.get("last_compaction_at")
    last_compacted_request_id = payload.get("last_compacted_request_id")

    return CompactionMeta(
        total_messages_seen=total_messages_seen if isinstance(total_messages_seen, int) else 0,
        total_messages_compacted=(
            total_messages_compacted if isinstance(total_messages_compacted, int) else 0
        ),
        last_compaction_at=last_compaction_at if isinstance(last_compaction_at, str) else None,
        last_compacted_request_id=(
            last_compacted_request_id if isinstance(last_compacted_request_id, str) else None
        ),
    )
