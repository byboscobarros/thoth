"""Canonical runtime envelopes for Thoth."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


DEFAULT_SCHEMA_VERSION = "v1"
SUPPORTED_SCHEMA_VERSIONS = frozenset({DEFAULT_SCHEMA_VERSION})


@dataclass(slots=True, frozen=True)
class EnvelopeValidationIssue:
    """Single deterministic validation issue item."""

    field: str
    message: str


class EnvelopeValidationError(ValueError):
    """Canonical envelope validation error with code and structured issues."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        issues: list[EnvelopeValidationIssue],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues


class RuntimeStatus(StrEnum):
    """Canonical runtime response status."""

    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"


class RuntimeMessageRole(StrEnum):
    """Canonical message roles used in runtime payloads."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(slots=True, frozen=True)
class RuntimeMessage:
    """Normalized message unit shared by input and output envelopes."""

    role: RuntimeMessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RuntimeInputEnvelope:
    """Canonical runtime input independent of gateway/source."""

    schema_version: str = DEFAULT_SCHEMA_VERSION
    request_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    gateway: str = ""
    actor: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    input: list[RuntimeMessage] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    policy_hints: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RuntimeOutputEnvelope:
    """Canonical runtime output consumed by every gateway adapter."""

    schema_version: str = DEFAULT_SCHEMA_VERSION
    request_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: RuntimeStatus = RuntimeStatus.SUCCESS
    messages: list[RuntimeMessage] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    memory_updates: list[dict[str, Any]] = field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = field(default_factory=list)
    audit_ref: str | None = None


def _validate_schema_version(schema_version: str) -> list[EnvelopeValidationIssue]:
    issues: list[EnvelopeValidationIssue] = []
    if not schema_version:
        issues.append(EnvelopeValidationIssue(field="schema_version", message="is required"))
        return issues

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_SCHEMA_VERSIONS))
        issues.append(
            EnvelopeValidationIssue(
                field="schema_version",
                message=f"unsupported version '{schema_version}', supported: {supported}",
            )
        )
    return issues


def _validate_required_text(field_name: str, value: str) -> list[EnvelopeValidationIssue]:
    if value.strip():
        return []
    return [EnvelopeValidationIssue(field=field_name, message="is required")]


def _raise_if_issues(issues: list[EnvelopeValidationIssue]) -> None:
    if not issues:
        return

    sorted_issues = sorted(issues, key=lambda issue: issue.field)
    raise EnvelopeValidationError(
        code="invalid_envelope",
        message="Envelope validation failed",
        issues=sorted_issues,
    )


def validate_input_envelope(envelope: RuntimeInputEnvelope) -> None:
    """Validate required input envelope contract fields."""

    issues: list[EnvelopeValidationIssue] = []
    issues.extend(_validate_schema_version(envelope.schema_version))
    issues.extend(_validate_required_text("request_id", envelope.request_id))
    issues.extend(_validate_required_text("gateway", envelope.gateway))
    _raise_if_issues(issues)


def validate_output_envelope(envelope: RuntimeOutputEnvelope) -> None:
    """Validate required output envelope contract fields."""

    issues: list[EnvelopeValidationIssue] = []
    issues.extend(_validate_schema_version(envelope.schema_version))
    issues.extend(_validate_required_text("request_id", envelope.request_id))
    _raise_if_issues(issues)
