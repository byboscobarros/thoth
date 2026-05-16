"""Session store port and in-memory adapter for the runtime."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from thoth.domain.session import SessionState


SESSION_FILE_SCHEMA_VERSION = "v1"


class SessionStore(Protocol):
    """Port for session persistence backends."""

    def create(self, state: SessionState) -> SessionState:
        """Create a new session state entry."""

    def get(self, session_id: str) -> SessionState | None:
        """Retrieve a session state by session id."""

    def save(self, state: SessionState) -> SessionState:
        """Persist a session state update."""


class InMemorySessionStore:
    """In-memory session store for local development and tests."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, state: SessionState) -> SessionState:
        if state.session_id in self._sessions:
            raise ValueError(f"session already exists: {state.session_id}")

        self._sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def save(self, state: SessionState) -> SessionState:
        self._sessions[state.session_id] = state
        return state


class FileSessionStore:
    """JSON file-backed session store for local persistent development."""

    def __init__(self, root_dir: str | Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def create(self, state: SessionState) -> SessionState:
        file_path = self._path_for_session(state.session_id)
        if file_path.exists():
            raise ValueError(f"session already exists: {state.session_id}")

        self._write_state(file_path, state)
        return state

    def get(self, session_id: str) -> SessionState | None:
        file_path = self._path_for_session(session_id)
        if not file_path.exists():
            return None

        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return _session_state_from_dict(payload)

    def save(self, state: SessionState) -> SessionState:
        file_path = self._path_for_session(state.session_id)
        self._write_state(file_path, state)
        return state

    def _path_for_session(self, session_id: str) -> Path:
        normalized = quote(session_id, safe="")
        return self._root_dir / f"{normalized}.json"

    def _write_state(self, file_path: Path, state: SessionState) -> None:
        payload = _session_state_to_dict(state)
        temp_path = file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        temp_path.replace(file_path)


def _session_state_to_dict(state: SessionState) -> dict[str, object]:
    return {
        "schema_version": SESSION_FILE_SCHEMA_VERSION,
        "session_id": state.session_id,
        "revision": state.revision,
        "metadata": state.metadata,
        "data": state.data,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


def _session_state_from_dict(payload: dict[str, object]) -> SessionState:
    schema_version = str(payload.get("schema_version", ""))
    if schema_version != SESSION_FILE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported session schema version '{schema_version}', "
            f"expected '{SESSION_FILE_SCHEMA_VERSION}'"
        )

    return SessionState(
        session_id=str(payload["session_id"]),
        revision=int(payload["revision"]),
        metadata=dict(payload.get("metadata", {})),
        data=dict(payload.get("data", {})),
        created_at=datetime.fromisoformat(str(payload["created_at"])),
        updated_at=datetime.fromisoformat(str(payload["updated_at"])),
    )
