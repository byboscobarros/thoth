"""Componentized mock provider implementation."""

from __future__ import annotations

from typing import Any

from thoth.domain.providers import (
    Provider,
    ProviderChunk,
    ProviderConfigurationError,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)
from thoth.providers.mock.components.completion import MockCompletionComponent
from thoth.providers.mock.components.streaming import MockStreamingComponent


class MockProvider(Provider):
    """Reference provider used for local development and contract tests."""

    def __init__(self) -> None:
        self._initialized = False
        self._completion = MockCompletionComponent()
        self._streaming = MockStreamingComponent()

    def initialize(self, context: dict[str, Any]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self._ensure_initialized()
        return self._completion.complete(request)

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        self._ensure_initialized()
        return self._streaming.stream(request)

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized, details="ready" if self._initialized else "not initialized")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise ProviderConfigurationError(
                code="provider.mock.not_initialized",
                message="mock provider must be initialized before execution",
            )
