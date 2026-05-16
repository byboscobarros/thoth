from thoth.domain.session import SessionState


def test_create_session_state_defaults() -> None:
    state = SessionState.create("sess_1")

    assert state.session_id == "sess_1"
    assert state.revision == 0
    assert state.created_at == state.updated_at
    assert state.metadata == {}
    assert state.data == {}


def test_with_metadata_increments_revision() -> None:
    state = SessionState.create("sess_1")

    updated = state.with_metadata({"tenant": "acme"})

    assert updated.revision == 1
    assert updated.metadata["tenant"] == "acme"
    assert updated.created_at == state.created_at
    assert updated.updated_at >= state.updated_at


def test_with_data_increments_revision_and_preserves_previous_values() -> None:
    state = SessionState.create("sess_1", data={"plan": "draft"})

    updated = state.with_data({"status": "running"})

    assert updated.revision == 1
    assert updated.data == {"plan": "draft", "status": "running"}


def test_invalid_session_id_raises_error() -> None:
    try:
        SessionState.create("   ")
    except ValueError as exc:
        assert str(exc) == "session_id is required"
    else:
        assert False, "Expected ValueError"
