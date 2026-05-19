from thoth.core.memory_scorer import MemoryScorer
from thoth.domain.memory import MemoryCandidate


def _candidate(*, content: str, role: str = "user") -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id="c1",
        request_id="r1",
        session_id="s1",
        source="input",
        event_type="turn.input",
        content=content,
        role=role,
    )


def test_memory_scorer_scores_preference_signal_higher() -> None:
    scorer = MemoryScorer()

    low = scorer.score(candidate=_candidate(content="mensagem qualquer", role="assistant"))
    high = scorer.score(candidate=_candidate(content="prefiro respostas objetivas", role="user"))

    assert high.value > low.value
    assert "preference_signal" in high.reason


def test_memory_scorer_boosts_repeated_signal() -> None:
    scorer = MemoryScorer()
    candidate = _candidate(content="prefiro respostas objetivas")

    first = scorer.score(candidate=candidate, previously_persisted_contents=set())
    repeated = scorer.score(
        candidate=candidate,
        previously_persisted_contents={"prefiro respostas objetivas"},
    )

    assert repeated.value > first.value
    assert "repeated_signal" in repeated.reason


def test_memory_scorer_penalizes_interrogative_question() -> None:
    scorer = MemoryScorer()

    score = scorer.score(candidate=_candidate(content="como eu prefiro minhas respostas?"))

    assert score.value < 0.50
    assert "interrogative_penalty" in score.reason
