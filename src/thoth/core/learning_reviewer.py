"""LLM-backed best-effort learning review for durable memory signals."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import ProviderExecutionError, ProviderRequest


class LearningReviewerPort(Protocol):
    """Reviewer contract used by MemoryManager for best-effort LLM review."""

    def review(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[str]:
        """Return durable memory candidates extracted by review."""


@dataclass(slots=True, frozen=True)
class LearningReviewerConfig:
    """Controls LLM review behavior."""

    max_suggestions: int = 3


class LLMLearningReviewer:
    """Provider-driven reviewer that extracts durable memory signals as JSON."""

    def __init__(
        self,
        *,
        provider_selector: ProviderSelector,
        provider_selection: ProviderSelectionConfig | None = None,
        model: str | None = None,
        config: LearningReviewerConfig | None = None,
    ) -> None:
        self._provider_selector = provider_selector
        self._provider_selection = provider_selection or ProviderSelectionConfig()
        self._model = model
        self._config = config or LearningReviewerConfig()

    def review(
        self,
        *,
        request_id: str,
        session_id: str,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[str]:
        selected_provider = self._provider_selector.select(
            capability="chat_completion",
            config=self._provider_selection,
        )

        request = ProviderRequest(
            request_id=f"{request_id}:learning_review",
            model=self._model,
            temperature=0.0,
            messages=self._build_messages(
                input_messages=input_messages,
                assistant_message=assistant_message,
            ),
            metadata={
                "component": "learning_reviewer",
                "session_id": session_id,
                "provider_id": selected_provider.provider_id,
            },
        )

        try:
            response = selected_provider.provider.execute(request)
        except ProviderExecutionError:
            return []

        return _parse_review_suggestions(
            output_text=response.output_text,
            max_suggestions=self._config.max_suggestions,
        )

    def _build_messages(
        self,
        *,
        input_messages: list[RuntimeMessage],
        assistant_message: str,
    ) -> list[RuntimeMessage]:
        system_prompt = (
            "You are a strict learning reviewer. Extract only durable memory signals. "
            "Return valid JSON only with schema: {\"memories\": string[]}. "
            "Do not include secrets, credentials, temporary environment failures, "
            "or one-off transient details."
        )

        payload = {
            "input_messages": [
                {"role": message.role.value, "content": message.content}
                for message in input_messages
            ],
            "assistant_message": assistant_message,
            "max_suggestions": self._config.max_suggestions,
        }

        return [
            RuntimeMessage(role=RuntimeMessageRole.SYSTEM, content=system_prompt),
            RuntimeMessage(role=RuntimeMessageRole.USER, content=json.dumps(payload, ensure_ascii=True)),
        ]


def _parse_review_suggestions(*, output_text: str, max_suggestions: int) -> list[str]:
    payload = _extract_json_object(output_text)
    if payload is None:
        return []

    memories = payload.get("memories")
    if not isinstance(memories, list):
        return []

    suggestions: list[str] = []
    seen: set[str] = set()
    for item in memories:
        if not isinstance(item, str):
            continue
        candidate = item.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        suggestions.append(candidate)
        if len(suggestions) >= max_suggestions:
            break
    return suggestions


def _extract_json_object(output_text: str) -> dict[str, object] | None:
    raw = output_text.strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
