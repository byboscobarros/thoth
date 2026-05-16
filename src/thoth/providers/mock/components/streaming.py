"""Deterministic streaming component used by the mock provider."""

from __future__ import annotations

from thoth.domain.providers import ProviderChunk, ProviderRequest


class MockStreamingComponent:
    """Generate deterministic streaming chunks for local tests."""

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        return [
            ProviderChunk(
                request_id=request.request_id,
                index=0,
                content_delta="[mock] ",
                done=False,
            ),
            ProviderChunk(
                request_id=request.request_id,
                index=1,
                content_delta="streaming response",
                done=True,
            ),
        ]
