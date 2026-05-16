"""Provider context rehydration using summary + active window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.session import SessionState
from thoth.domain.session_compaction import summary_from_data


@dataclass(slots=True, frozen=True)
class ProviderContextConfig:
    """Context sizing controls for provider requests."""

    provider_context_limit: int = 40
    max_summary_chars: int = 1200


class ProviderContextBuilder:
    """Build compact provider context from session summary and active history."""

    def __init__(self, config: ProviderContextConfig | None = None) -> None:
        self._config = config or ProviderContextConfig()

    def build(
        self,
        *,
        session_state: SessionState,
        input_messages: list[RuntimeMessage],
    ) -> list[RuntimeMessage]:
        summary_messages = self._build_summary_messages(session_state.data)
        history_messages = self._history_messages(session_state.data.get("message_history"))

        budget = self._config.provider_context_limit - len(summary_messages) - len(input_messages)
        if budget < 0:
            budget = 0

        context_tail = history_messages[-budget:] if budget > 0 else []
        return [*summary_messages, *context_tail, *input_messages]

    def _build_summary_messages(self, data: dict[str, Any]) -> list[RuntimeMessage]:
        summary = summary_from_data(data)
        if not summary.short.strip():
            return []

        short_text = summary.short.strip()
        if len(short_text) > self._config.max_summary_chars:
            short_text = short_text[: self._config.max_summary_chars - 3].rstrip() + "..."

        lines: list[str] = ["Resumo da sessao:", short_text]
        structured_lines: list[str] = []
        for key, title in [
            ("facts", "Fatos"),
            ("goals", "Objetivos"),
            ("decisions", "Decisoes"),
            ("open_tasks", "Pendencias"),
        ]:
            values = summary.structured.get(key, [])
            if not values:
                continue
            structured_lines.append(f"{title}: {values[0]}")

        if structured_lines:
            lines.append("Contexto estruturado:")
            lines.extend(structured_lines[:4])

        content = "\n".join(lines)
        return [RuntimeMessage(role=RuntimeMessageRole.SYSTEM, content=content)]

    @staticmethod
    def _history_messages(raw_history: Any) -> list[RuntimeMessage]:
        messages: list[RuntimeMessage] = []
        if not isinstance(raw_history, list):
            return messages

        for item in raw_history:
            if not isinstance(item, dict):
                continue

            role_raw = item.get("role")
            content_raw = item.get("content")
            if not isinstance(role_raw, str) or not isinstance(content_raw, str):
                continue
            if not content_raw.strip():
                continue

            try:
                role = RuntimeMessageRole(role_raw)
            except ValueError:
                continue
            messages.append(RuntimeMessage(role=role, content=content_raw))

        return messages
