"""Session lifecycle coordinator for runtime state."""

from __future__ import annotations

from threading import Lock
from typing import Any, Mapping

from thoth.core.session_store import SessionStore
from thoth.domain.session import SessionState


class SessionManager:
    """Manage canonical session state lifecycle with per-session locking."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self._lock_map: dict[str, Lock] = {}
        self._lock_map_guard = Lock()

    def get_or_create(
        self,
        session_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> SessionState:
        """Load an existing session or atomically create a new one."""

        if not session_id.strip():
            raise ValueError("session_id is required")

        session_lock = self._get_session_lock(session_id)
        with session_lock:
            existing = self._store.get(session_id)
            if existing is not None:
                return existing

            candidate = SessionState.create(
                session_id,
                metadata=metadata,
                data=data,
            )
            try:
                return self._store.create(candidate)
            except ValueError:
                # Defensive fallback when backend reports duplicate creation.
                existing_after_race = self._store.get(session_id)
                if existing_after_race is not None:
                    return existing_after_race
                raise

    def persist(self, state: SessionState) -> SessionState:
        """Persist a session update with per-session synchronization."""

        session_lock = self._get_session_lock(state.session_id)
        with session_lock:
            return self._store.save(state)

    def _get_session_lock(self, session_id: str) -> Lock:
        with self._lock_map_guard:
            lock = self._lock_map.get(session_id)
            if lock is None:
                lock = Lock()
                self._lock_map[session_id] = lock
            return lock
