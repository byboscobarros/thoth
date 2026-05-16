"""Canonical provider contracts and payload models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from thoth.domain.envelopes import RuntimeMessage


@dataclass(slots=True, frozen=True)
class ProviderRequest:
    """Canonical provider execution request."""

    request_id: str
    messages: list[RuntimeMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProviderChunk:
    """Canonical chunk emitted during provider streaming."""

    request_id: str
    index: int
    content_delta: str
    done: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProviderResponse:
    """Canonical provider execution response."""

    request_id: str
    output_text: str
    messages: list[RuntimeMessage] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProviderHealth:
    """Provider healthcheck result."""

    ok: bool
    details: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Base provider exception with canonical error code."""

    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ProviderConfigurationError(ProviderError):
    """Raised when provider configuration is invalid or missing."""


class ProviderExecutionError(ProviderError):
    """Raised when provider execution fails at runtime."""


class Provider(Protocol):
    """Canonical provider interface expected by the runtime."""

    def initialize(self, context: dict[str, Any]) -> None:
        """Initialize provider resources from runtime context."""

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Execute a non-streaming request."""

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        """Execute a streaming request and return canonical chunks."""

    def shutdown(self) -> None:
        """Release provider resources."""

    def healthcheck(self) -> ProviderHealth:
        """Return provider health status for registration/runtime checks."""
