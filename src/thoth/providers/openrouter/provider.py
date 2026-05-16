"""OpenRouter provider implementation."""

from __future__ import annotations

import os
from typing import Any

from thoth.domain.providers import (
    Provider,
    ProviderChunk,
    ProviderConfigurationError,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)
from thoth.providers.openrouter.components.completion import OpenRouterCompletionComponent
from thoth.providers.openrouter.components.streaming import OpenRouterStreamingComponent


class OpenRouterProvider(Provider):
    """Provider implementation for OpenRouter Chat Completions API."""

    def __init__(self) -> None:
        self._initialized = False
        self._configured = False
        self._configuration_reason = "provider not initialized"
        self._completion: OpenRouterCompletionComponent | None = None
        self._streaming: OpenRouterStreamingComponent | None = None

    def initialize(self, context: dict[str, Any]) -> None:
        _ = context
        api_key = os.getenv("THOTH_OPENROUTER_API_KEY", "").strip()
        base_url = os.getenv("THOTH_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
        default_model = os.getenv("THOTH_OPENROUTER_MODEL", "openai/gpt-5.2").strip()
        http_referer = os.getenv("THOTH_OPENROUTER_HTTP_REFERER", "").strip() or None
        app_title = os.getenv("THOTH_OPENROUTER_TITLE", "").strip() or None
        timeout_seconds = _read_timeout_seconds()

        self._completion = OpenRouterCompletionComponent(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            http_referer=http_referer,
            app_title=app_title,
        )
        self._streaming = OpenRouterStreamingComponent(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            http_referer=http_referer,
            app_title=app_title,
        )

        self._initialized = True
        self._configured = bool(api_key)
        self._configuration_reason = (
            "ready" if self._configured else "missing THOTH_OPENROUTER_API_KEY"
        )

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self._ensure_ready()
        assert self._completion is not None
        return self._completion.complete(request)

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        self._ensure_ready()
        assert self._streaming is not None
        return self._streaming.stream(request)

    def shutdown(self) -> None:
        self._initialized = False
        self._configured = False
        self._configuration_reason = "provider shutdown"

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            ok=self._initialized and self._configured,
            details=self._configuration_reason,
        )

    def _ensure_ready(self) -> None:
        if not self._initialized:
            raise ProviderConfigurationError(
                code="provider.openrouter.not_initialized",
                message="openrouter provider must be initialized before execution",
            )
        if not self._configured:
            raise ProviderConfigurationError(
                code="provider.openrouter.not_configured",
                message="missing THOTH_OPENROUTER_API_KEY",
            )


def _read_timeout_seconds() -> float:
    raw_timeout = os.getenv("THOTH_OPENROUTER_TIMEOUT_SECONDS", "60").strip()
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return 60.0
    if timeout <= 0:
        return 60.0
    return timeout
