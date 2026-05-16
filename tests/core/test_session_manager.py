from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from thoth.core.session_manager import SessionManager
from thoth.core.session_store import InMemorySessionStore


def test_get_or_create_creates_session_when_missing() -> None:
    manager = SessionManager(InMemorySessionStore())

    state = manager.get_or_create("sess_1", metadata={"tenant": "acme"})

    assert state.session_id == "sess_1"
    assert state.revision == 0
    assert state.metadata["tenant"] == "acme"


def test_get_or_create_returns_existing_session() -> None:
    manager = SessionManager(InMemorySessionStore())

    first = manager.get_or_create("sess_1")
    second = manager.get_or_create("sess_1")

    assert first == second


def test_persist_saves_new_revision() -> None:
    manager = SessionManager(InMemorySessionStore())

    initial = manager.get_or_create("sess_1")
    updated = initial.with_data({"status": "running"})
    manager.persist(updated)

    loaded = manager.get_or_create("sess_1")
    assert loaded.revision == 1
    assert loaded.data["status"] == "running"


def test_get_or_create_is_safe_under_local_concurrency() -> None:
    manager = SessionManager(InMemorySessionStore())

    def worker() -> str:
        return manager.get_or_create("sess_concurrent").session_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: worker(), range(32)))

    assert results == ["sess_concurrent"] * 32


def test_get_or_create_rejects_blank_session_id() -> None:
    manager = SessionManager(InMemorySessionStore())

    try:
        manager.get_or_create(" ")
    except ValueError as exc:
        assert str(exc) == "session_id is required"
    else:
        assert False, "Expected ValueError"
