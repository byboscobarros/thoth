"""Heuristic scorer for learning memory candidates."""

from __future__ import annotations

from dataclasses import dataclass

from thoth.domain.memory import MemoryCandidate, MemoryScore


@dataclass(slots=True, frozen=True)
class MemoryScorerConfig:
    """Thresholds and heuristics for memory relevance scoring."""

    persist_threshold: float = 0.70
    review_threshold: float = 0.50


class MemoryScorer:
    """Deterministic scorer based on stable textual signals."""

    _PREFERENCE_TERMS = (
        "prefiro",
        "preferencia",
        "gosto",
        "quero",
        "preciso",
        "sempre",
        "nunca",
    )
    _GOAL_TERMS = (
        "objetivo",
        "meta",
        "entregar",
        "implementar",
        "fazer",
    )
    _DECISION_TERMS = (
        "decid",
        "vamos seguir",
        "padrao",
        "combinado",
        "definido",
    )
    _QUESTION_STARTERS = (
        "como",
        "qual",
        "quais",
        "o que",
        "por que",
        "pq",
        "quando",
        "onde",
    )

    def __init__(self, config: MemoryScorerConfig | None = None) -> None:
        self._config = config or MemoryScorerConfig()

    def score(
        self,
        *,
        candidate: MemoryCandidate,
        previously_persisted_contents: set[str] | None = None,
    ) -> MemoryScore:
        text = candidate.content.strip().lower()
        previous = previously_persisted_contents or set()

        score = 0.20
        reasons: list[str] = ["base"]

        if candidate.role == "user":
            score += 0.20
            reasons.append("user_signal")

        if any(term in text for term in self._PREFERENCE_TERMS):
            score += 0.30
            reasons.append("preference_signal")

        if any(term in text for term in self._GOAL_TERMS):
            score += 0.20
            reasons.append("goal_signal")

        if any(term in text for term in self._DECISION_TERMS):
            score += 0.20
            reasons.append("decision_signal")

        if text in previous:
            score += 0.10
            reasons.append("repeated_signal")

        if self._looks_like_interrogative_prompt(text):
            score -= 0.40
            reasons.append("interrogative_penalty")

        bounded = max(0.0, min(1.0, score))
        return MemoryScore(value=bounded, reason=",".join(reasons))

    def _looks_like_interrogative_prompt(self, text: str) -> bool:
        if "?" not in text:
            return False

        compact = " ".join(text.split())
        return compact.startswith(self._QUESTION_STARTERS)
