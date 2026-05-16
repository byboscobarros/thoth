"""Provider manifest models and validation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from thoth.domain.providers import ProviderConfigurationError

SUPPORTED_PROVIDER_MANIFEST_SCHEMA_VERSIONS = frozenset({"v1"})


@dataclass(slots=True, frozen=True)
class ProviderManifestValidationIssue:
    """Single deterministic provider manifest validation issue."""

    field: str
    message: str


class ProviderManifestValidationError(ProviderConfigurationError):
    """Raised when provider manifest validation fails."""

    def __init__(self, *, issues: list[ProviderManifestValidationIssue]) -> None:
        super().__init__(code="provider.manifest.invalid", message="Provider manifest validation failed")
        self.issues = issues


@dataclass(slots=True, frozen=True)
class ProviderManifest:
    """Canonical provider manifest used by loader and registry."""

    schema_version: str
    type: str
    name: str
    version: str
    entrypoint: str
    capabilities: dict[str, bool]
    compatibility: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_provider_manifest(payload: Mapping[str, Any]) -> ProviderManifest:
    """Validate and normalize provider manifest payload."""

    issues: list[ProviderManifestValidationIssue] = []

    schema_version = _read_required_str(payload, "schema_version", issues)
    manifest_type = _read_required_str(payload, "type", issues)
    name = _read_required_str(payload, "name", issues)
    version = _read_required_str(payload, "version", issues)
    entrypoint = _read_required_str(payload, "entrypoint", issues)

    if schema_version and schema_version not in SUPPORTED_PROVIDER_MANIFEST_SCHEMA_VERSIONS:
        supported_versions = ", ".join(sorted(SUPPORTED_PROVIDER_MANIFEST_SCHEMA_VERSIONS))
        issues.append(
            ProviderManifestValidationIssue(
                field="schema_version",
                message=f"unsupported version '{schema_version}', supported: {supported_versions}",
            )
        )

    if manifest_type and manifest_type != "provider":
        issues.append(
            ProviderManifestValidationIssue(field="type", message="must be 'provider'")
        )

    capabilities_raw = payload.get("capabilities")
    capabilities: dict[str, bool] = {}
    if not isinstance(capabilities_raw, dict) or not capabilities_raw:
        issues.append(
            ProviderManifestValidationIssue(
                field="capabilities",
                message="must be a non-empty object",
            )
        )
    else:
        for capability, enabled in capabilities_raw.items():
            if not isinstance(capability, str) or not capability.strip():
                issues.append(
                    ProviderManifestValidationIssue(
                        field="capabilities",
                        message="all capability keys must be non-empty strings",
                    )
                )
                continue
            if not isinstance(enabled, bool):
                issues.append(
                    ProviderManifestValidationIssue(
                        field=f"capabilities.{capability}",
                        message="must be boolean",
                    )
                )
                continue
            capabilities[capability] = enabled

    compatibility_raw = payload.get("compatibility")
    compatibility: dict[str, Any] = {}
    if not isinstance(compatibility_raw, dict):
        issues.append(
            ProviderManifestValidationIssue(
                field="compatibility",
                message="must be an object",
            )
        )
    else:
        compatibility = dict(compatibility_raw)

    metadata_raw = payload.get("metadata", {})
    metadata: dict[str, Any] = {}
    if isinstance(metadata_raw, dict):
        metadata = dict(metadata_raw)
    else:
        issues.append(ProviderManifestValidationIssue(field="metadata", message="must be an object"))

    if issues:
        raise ProviderManifestValidationError(issues=sorted(issues, key=lambda issue: issue.field))

    return ProviderManifest(
        schema_version=schema_version,
        type=manifest_type,
        name=name,
        version=version,
        entrypoint=entrypoint,
        capabilities=capabilities,
        compatibility=compatibility,
        metadata=metadata,
    )


def load_provider_manifest(path: str | Path) -> ProviderManifest:
    """Load and validate provider manifest from JSON file."""

    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderConfigurationError(
            code="provider.manifest.missing",
            message=f"manifest not found: {manifest_path}",
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProviderConfigurationError(
            code="provider.manifest.invalid_json",
            message=f"manifest has invalid json: {manifest_path}",
        ) from exc

    if not isinstance(payload, dict):
        raise ProviderConfigurationError(
            code="provider.manifest.invalid",
            message="manifest root must be an object",
        )

    return validate_provider_manifest(payload)


def _read_required_str(
    payload: Mapping[str, Any],
    field_name: str,
    issues: list[ProviderManifestValidationIssue],
) -> str:
    value = payload.get(field_name)
    if isinstance(value, str) and value.strip():
        return value

    issues.append(ProviderManifestValidationIssue(field=field_name, message="is required"))
    return ""
