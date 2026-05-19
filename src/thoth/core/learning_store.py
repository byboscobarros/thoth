"""Global learning store for cross-session memory persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class LearningStore(Protocol):
    """Port for global learning persistence independent of session state."""

    def load(self) -> list[dict[str, Any]]:
        """Load persisted learning updates."""

    def append(self, updates: list[dict[str, Any]]) -> None:
        """Append new learning updates to persistent storage."""


class InMemoryLearningStore:
    """In-memory learning store, useful for tests and ephemeral runs."""

    def __init__(self, *, max_updates: int = 5000) -> None:
        self._updates: list[dict[str, Any]] = []
        self._max_updates = max_updates

    def load(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._updates]

    def append(self, updates: list[dict[str, Any]]) -> None:
        for item in updates:
            if isinstance(item, dict):
                self._updates.append(dict(item))
        if self._max_updates > 0:
            self._updates = self._updates[-self._max_updates :]


class FileLearningStore:
    """JSON file-backed global learning store."""

    def __init__(self, path: str | Path, *, max_updates: int = 5000) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_updates = max_updates

    def load(self) -> list[dict[str, Any]]:
        if not self._path.exists() or not self._path.is_file():
            return []

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return []

        updates = payload.get("updates")
        if not isinstance(updates, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in updates:
            if isinstance(item, dict):
                normalized.append(dict(item))
        return normalized

    def append(self, updates: list[dict[str, Any]]) -> None:
        existing = self.load()
        for item in updates:
            if isinstance(item, dict):
                existing.append(dict(item))

        if self._max_updates > 0:
            existing = existing[-self._max_updates :]

        payload = {
            "schema_version": "v1",
            "updates": existing,
        }

        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        temp_path.replace(self._path)
