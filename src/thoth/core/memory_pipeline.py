"""Learning memory pipeline: capture, score, redact, decide."""

from __future__ import annotations

from dataclasses import dataclass

from thoth.core.memory_redactor import MemoryRedactor
from thoth.core.memory_scorer import MemoryScorer, MemoryScorerConfig
from thoth.domain.envelopes import RuntimeMessage
from thoth.domain.memory import MemoryCandidate, MemoryDecision, MemoryUpdate


@dataclass(slots=True, frozen=True)
class MemoryPipelineConfig:
    """Configuration for learning capture and decision steps."""

    persist_threshold: float = 0.70
    review_threshold: float = 0.50
    max_candidates: int = 10


class MemoryPipeline:
    """Deterministic memory learning pipeline."""

    def __init__(
        self,
        *,
        config: MemoryPipelineConfig | None = None,
        scorer: MemoryScorer | None = None,
        redactor: MemoryRedactor | None = None,
    ) -> None:
        self._config = config or MemoryPipelineConfig()
        self._scorer = scorer or MemoryScorer(
            MemoryScorerConfig(
                persist_threshold=self._config.persist_threshold,
                review_threshold=self._config.review_threshold,
            )
        )
        self._redactor = redactor or MemoryRedactor()

    def process(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
        session_summary: str,
        previously_persisted_contents: set[str] | None = None,
    ) -> tuple[list[MemoryCandidate], list[MemoryUpdate]]:
        candidates = self._capture_candidates(
            request_id=request_id,
            session_id=session_id,
            input_messages=input_messages,
            assistant_message=assistant_message,
            session_summary=session_summary,
        )
        updates: list[MemoryUpdate] = []
        for candidate in candidates:
            score = self._scorer.score(
                candidate=candidate,
                previously_persisted_contents=previously_persisted_contents,
            )
            redaction = self._redactor.redact(candidate.content)
            decision = self._decide(score.value)
            updates.append(
                MemoryUpdate(
                    candidate_id=candidate.candidate_id,
                    request_id=candidate.request_id,
                    session_id=candidate.session_id,
                    source=candidate.source,
                    event_type=candidate.event_type,
                    content=redaction.content,
                    score=score.value,
                    redaction_applied=redaction.applied,
                    decision=decision,
                    reason=score.reason,
                )
            )
        return candidates, updates

    def _capture_candidates(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
        session_summary: str,
    ) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        index = 0

        for message in input_messages:
            content = message.content.strip()
            if not content:
                continue
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"{request_id}:in:{index}",
                    request_id=request_id,
                    session_id=session_id,
                    source="input",
                    event_type="turn.input",
                    content=content,
                    role=message.role.value,
                )
            )
            index += 1
            if len(candidates) >= self._config.max_candidates:
                return candidates

        if assistant_message.strip() and len(candidates) < self._config.max_candidates:
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"{request_id}:assistant:{index}",
                    request_id=request_id,
                    session_id=session_id,
                    source="assistant",
                    event_type="turn.output",
                    content=assistant_message.strip(),
                    role="assistant",
                )
            )
            index += 1

        if session_summary.strip() and len(candidates) < self._config.max_candidates:
            candidates.append(
                MemoryCandidate(
                    candidate_id=f"{request_id}:summary:{index}",
                    request_id=request_id,
                    session_id=session_id,
                    source="session_summary",
                    event_type="session.summary",
                    content=session_summary.strip(),
                    role="system",
                )
            )

        return candidates

    def _decide(self, score: float) -> MemoryDecision:
        if score >= self._config.persist_threshold:
            return MemoryDecision.PERSIST
        if score >= self._config.review_threshold:
            return MemoryDecision.REVIEW
        return MemoryDecision.DISCARD
