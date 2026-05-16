from __future__ import annotations

import json
from pathlib import Path

import pytest

from thoth.domain.provider_manifest import (
    ProviderManifestValidationError,
    load_provider_manifest,
    validate_provider_manifest,
)
from thoth.domain.providers import ProviderConfigurationError


def test_validate_provider_manifest_success() -> None:
    manifest = validate_provider_manifest(
        {
            "schema_version": "v1",
            "type": "provider",
            "name": "mock",
            "version": "0.1.0",
            "entrypoint": "thoth.providers.mock.provider:MockProvider",
            "capabilities": {"chat_completion": True, "streaming": False},
            "compatibility": {"runtime": ">=0.1.0"},
        }
    )

    assert manifest.name == "mock"
    assert manifest.capabilities["chat_completion"] is True


def test_validate_provider_manifest_invalid_type_raises() -> None:
    with pytest.raises(ProviderManifestValidationError) as exc:
        validate_provider_manifest(
            {
                "schema_version": "v1",
                "type": "tool",
                "name": "mock",
                "version": "0.1.0",
                "entrypoint": "x:y",
                "capabilities": {"chat_completion": True},
                "compatibility": {},
            }
        )

    assert exc.value.code == "provider.manifest.invalid"
    assert exc.value.issues[0].field == "type"


def test_load_provider_manifest_reads_and_validates_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    payload = {
        "schema_version": "v1",
        "type": "provider",
        "name": "mock",
        "version": "0.1.0",
        "entrypoint": "thoth.providers.mock.provider:MockProvider",
        "capabilities": {"chat_completion": True},
        "compatibility": {},
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_provider_manifest(manifest_path)

    assert manifest.entrypoint == "thoth.providers.mock.provider:MockProvider"


def test_load_provider_manifest_invalid_json_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ProviderConfigurationError) as exc:
        load_provider_manifest(manifest_path)

    assert exc.value.code == "provider.manifest.invalid_json"
