"""Deterministic completion component used by the mock provider."""

from __future__ import annotations

from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import ProviderRequest, ProviderResponse


class MockCompletionComponent:
    """Generate deterministic completion outputs for local tests."""

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        last_user_message = ""
        for message in reversed(request.messages):
            if message.role is RuntimeMessageRole.USER:
                last_user_message = message.content
                break

        text = f"[mock] echo: {last_user_message}" if last_user_message else "[mock] ready"
        return ProviderResponse(
            request_id=request.request_id,
            output_text=text,
            messages=[RuntimeMessage(role=RuntimeMessageRole.ASSISTANT, content=text)],
            usage={"input_tokens": len(request.messages), "output_tokens": 1},
            metadata={"component": "completion"},
        )
