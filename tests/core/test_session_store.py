from pathlib import Path

from thoth.core.session_store import FileSessionStore, InMemorySessionStore
from thoth.domain.session import SessionState


def test_create_and_get_session() -> None:
    store = InMemorySessionStore()
    state = SessionState.create("sess_1")

    store.create(state)
    loaded = store.get("sess_1")

    assert loaded is not None
    assert loaded.session_id == "sess_1"
    assert loaded.revision == 0


def test_save_updates_existing_session() -> None:
    store = InMemorySessionStore()
    initial = SessionState.create("sess_1", data={"step": "draft"})
    store.create(initial)

    updated = initial.with_data({"step": "running"})
    store.save(updated)

    loaded = store.get("sess_1")
    assert loaded is not None
    assert loaded.revision == 1
    assert loaded.data["step"] == "running"


def test_create_duplicate_session_raises_error() -> None:
    store = InMemorySessionStore()
    state = SessionState.create("sess_1")

    store.create(state)

    try:
        store.create(state)
    except ValueError as exc:
        assert str(exc) == "session already exists: sess_1"
    else:
        assert False, "Expected ValueError"


def test_file_session_store_persists_state(tmp_path: Path) -> None:
    store = FileSessionStore(tmp_path)
    initial = SessionState.create("sess_file", data={"step": "draft"})

    store.create(initial)
    updated = initial.with_data({"step": "running"})
    store.save(updated)

    loaded = store.get("sess_file")
    assert loaded is not None
    assert loaded.revision == 1
    assert loaded.data["step"] == "running"


def test_file_session_store_survives_new_instance(tmp_path: Path) -> None:
    first_store = FileSessionStore(tmp_path)
    first_store.create(SessionState.create("sess_shared"))

    second_store = FileSessionStore(tmp_path)
    loaded = second_store.get("sess_shared")

    assert loaded is not None
    assert loaded.session_id == "sess_shared"
