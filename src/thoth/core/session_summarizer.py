"""Session summary strategy contracts and built-in implementations."""

from __future__ import annotations

import json
from typing import Protocol

from thoth.core.provider_selector import ProviderSelectionConfig, ProviderSelector
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import ProviderExecutionError, ProviderRequest
from thoth.domain.session_compaction import SessionSummary


class SessionSummarizer(Protocol):
    """Strategy contract for generating session summaries."""

    def summarize(
        self,
        *,
        previous_summary: SessionSummary,
        compacted_history: list[dict[str, str]],
        max_summary_chars: int,
    ) -> SessionSummary:
        """Return an updated session summary from compacted history."""


class HeuristicSessionSummarizer:
    """Deterministic rule-based summarizer used as default."""

    def summarize(
        self,
        *,
        previous_summary: SessionSummary,
        compacted_history: list[dict[str, str]],
        max_summary_chars: int,
    ) -> SessionSummary:
        extracted = _extract_structured_signals(compacted_history)

        merged_structured: dict[str, list[str]] = {}
        for key in ["facts", "goals", "decisions", "open_tasks"]:
            merged_structured[key] = _merge_unique(
                previous_summary.structured.get(key, []),
                extracted.get(key, []),
            )

        short_summary = _build_short_summary(
            compacted_history=compacted_history,
            structured=merged_structured,
            max_summary_chars=max_summary_chars,
        )
        return SessionSummary(version=1, short=short_summary, structured=merged_structured)


class LLMSessionSummarizer:
    """LLM-backed summarizer with safe fallback to heuristic strategy."""

    _PROMPT_VERSION = "v1"

    def __init__(
        self,
        *,
        provider_selector: ProviderSelector | None = None,
        provider_selection: ProviderSelectionConfig | None = None,
        model: str | None = None,
        fallback: SessionSummarizer | None = None,
    ) -> None:
        self._provider_selector = provider_selector
        self._provider_selection = provider_selection or ProviderSelectionConfig()
        self._model = model
        self._fallback = fallback or HeuristicSessionSummarizer()

    def summarize(
        self,
        *,
        previous_summary: SessionSummary,
        compacted_history: list[dict[str, str]],
        max_summary_chars: int,
    ) -> SessionSummary:
        if self._provider_selector is None:
            return self._fallback.summarize(
                previous_summary=previous_summary,
                compacted_history=compacted_history,
                max_summary_chars=max_summary_chars,
            )

        try:
            selected_provider = self._provider_selector.select(
                capability="chat_completion",
                config=self._provider_selection,
            )
            provider_response = selected_provider.provider.execute(
                ProviderRequest(
                    request_id="session_summarizer",
                    model=self._model,
                    temperature=0.0,
                    messages=self._build_messages(
                        previous_summary=previous_summary,
                        compacted_history=compacted_history,
                        max_summary_chars=max_summary_chars,
                    ),
                    metadata={
                        "component": "session_summarizer",
                        "prompt_version": self._PROMPT_VERSION,
                        "provider_id": selected_provider.provider_id,
                    },
                )
            )
            return _parse_summary_from_output(
                output_text=provider_response.output_text,
                fallback=self._fallback,
                previous_summary=previous_summary,
                compacted_history=compacted_history,
                max_summary_chars=max_summary_chars,
            )
        except ProviderExecutionError:
            return self._fallback.summarize(
                previous_summary=previous_summary,
                compacted_history=compacted_history,
                max_summary_chars=max_summary_chars,
            )

    def _build_messages(
        self,
        *,
        previous_summary: SessionSummary,
        compacted_history: list[dict[str, str]],
        max_summary_chars: int,
    ) -> list[RuntimeMessage]:
        system_prompt = (
            "You are a strict session summarizer. "
            "Return only valid JSON, with no markdown. "
            "Schema: {\"short\": string, \"structured\": "
            "{\"facts\": string[], \"goals\": string[], \"decisions\": string[], "
            "\"open_tasks\": string[]}}. "
            "Keep short concise and <= max_summary_chars. "
            "Avoid secrets and personal sensitive data."
        )
        payload = {
            "prompt_version": self._PROMPT_VERSION,
            "max_summary_chars": max_summary_chars,
            "previous_summary": previous_summary.to_dict(),
            "compacted_history": compacted_history,
        }
        return [
            RuntimeMessage(role=RuntimeMessageRole.SYSTEM, content=system_prompt),
            RuntimeMessage(
                role=RuntimeMessageRole.USER,
                content=json.dumps(payload, ensure_ascii=True),
            ),
        ]


def _parse_summary_from_output(
    *,
    output_text: str,
    fallback: SessionSummarizer,
    previous_summary: SessionSummary,
    compacted_history: list[dict[str, str]],
    max_summary_chars: int,
) -> SessionSummary:
    payload = _extract_json_object(output_text)
    if payload is None:
        return fallback.summarize(
            previous_summary=previous_summary,
            compacted_history=compacted_history,
            max_summary_chars=max_summary_chars,
        )

    short = payload.get("short")
    structured = payload.get("structured")
    if not isinstance(short, str) or not isinstance(structured, dict):
        return fallback.summarize(
            previous_summary=previous_summary,
            compacted_history=compacted_history,
            max_summary_chars=max_summary_chars,
        )

    return SessionSummary(version=1, short=short, structured=structured)


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

    candidate = raw[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _extract_structured_signals(compacted_history: list[dict[str, str]]) -> dict[str, list[str]]:
    facts: list[str] = []
    goals: list[str] = []
    decisions: list[str] = []
    open_tasks: list[str] = []

    for item in compacted_history:
        role = item["role"].strip().lower()
        content = item["content"].strip()
        lowered = content.lower()

        if role == "user":
            if "?" in content or any(
                term in lowered for term in ["quero", "preciso", "como", "pode"]
            ):
                goals.append(content)
            else:
                facts.append(content)
            if any(
                term in lowered for term in ["falta", "pendente", "todo", "implemente", "fazer"]
            ):
                open_tasks.append(content)

        if role == "assistant" and any(
            term in lowered for term in ["feito", "implementado", "decid", "vamos seguir", "conclu"]
        ):
            decisions.append(content)

    return {
        "facts": facts[:8],
        "goals": goals[:8],
        "decisions": decisions[:8],
        "open_tasks": open_tasks[:8],
    }


def _build_short_summary(
    *,
    compacted_history: list[dict[str, str]],
    structured: dict[str, list[str]],
    max_summary_chars: int,
) -> str:
    snippets: list[str] = []

    if structured.get("goals"):
        snippets.append(f"Objetivos: {structured['goals'][0]}")
    if structured.get("facts"):
        snippets.append(f"Fatos: {structured['facts'][0]}")
    if structured.get("open_tasks"):
        snippets.append(f"Pendencias: {structured['open_tasks'][0]}")
    if structured.get("decisions"):
        snippets.append(f"Decisoes: {structured['decisions'][0]}")

    if not snippets:
        for item in compacted_history[-4:]:
            role = item["role"]
            content = item["content"].strip()
            if content:
                snippets.append(f"{role}: {content}")

    summary = " | ".join(snippets).strip()
    if len(summary) <= max_summary_chars:
        return summary
    return summary[: max_summary_chars - 3].rstrip() + "..."


def _merge_unique(current: list[str], new_items: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for item in [*current, *new_items]:
        candidate = item.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        merged.append(candidate)
    return merged[:20]
