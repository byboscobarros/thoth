"""Session domain model for canonical runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Mapping


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, frozen=True)
class SessionState:
    """Canonical runtime session state with revision tracking."""

    session_id: str
    revision: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        if self.revision < 0:
            raise ValueError("revision must be >= 0")

        # Defensive copies avoid external mutation through shared references.
        object.__setattr__(self, "metadata", dict(self.metadata))
        object.__setattr__(self, "data", dict(self.data))

    @classmethod
    def create(
        cls,
        session_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> SessionState:
        now = _utc_now()
        return cls(
            session_id=session_id,
            revision=0,
            metadata=dict(metadata or {}),
            data=dict(data or {}),
            created_at=now,
            updated_at=now,
        )

    def with_metadata(self, metadata: Mapping[str, Any]) -> SessionState:
        merged_metadata = {**self.metadata, **dict(metadata)}
        return replace(
            self,
            revision=self.revision + 1,
            metadata=merged_metadata,
            updated_at=_utc_now(),
        )

    def with_data(self, data: Mapping[str, Any]) -> SessionState:
        merged_data = {**self.data, **dict(data)}
        return replace(
            self,
            revision=self.revision + 1,
            data=merged_data,
            updated_at=_utc_now(),
        )
