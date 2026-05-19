from thoth.domain.memory import LearningTriggerState, MemoryCandidate, MemoryDecision, MemoryUpdate


def test_memory_candidate_to_dict_contains_required_fields() -> None:
    candidate = MemoryCandidate(
        candidate_id="c1",
        request_id="r1",
        session_id="s1",
        source="input",
        event_type="turn.input",
        content="prefiro respostas curtas",
        role="user",
    )

    payload = candidate.to_dict()

    assert payload["candidate_id"] == "c1"
    assert payload["request_id"] == "r1"
    assert payload["session_id"] == "s1"
    assert payload["source"] == "input"


def test_memory_update_to_dict_serializes_decision_value() -> None:
    update = MemoryUpdate(
        candidate_id="c2",
        request_id="r2",
        session_id="s2",
        source="assistant",
        event_type="turn.output",
        content="vamos seguir com arquitetura modular",
        score=0.9,
        redaction_applied=False,
        decision=MemoryDecision.PERSIST,
        reason="user_signal,decision_signal",
    )

    payload = update.to_dict()

    assert payload["decision"] == "persist"
    assert payload["score"] == 0.9


def test_learning_trigger_state_to_dict() -> None:
    state = LearningTriggerState(turns_since_memory=3, iterations_since_skill_signal=7)

    payload = state.to_dict()

    assert payload == {"turns_since_memory": 3, "iterations_since_skill_signal": 7}
