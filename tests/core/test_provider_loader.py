from __future__ import annotations

import json
from pathlib import Path

from thoth.core.provider_loader import ProviderLoader
from thoth.core.provider_registry import ProviderRegistry


def test_provider_loader_loads_mock_provider() -> None:
    registry = ProviderRegistry()
    loader = ProviderLoader(registry)

    report = loader.load_from_paths(
        search_paths=[Path("src/thoth/providers")],
        context={"mode": "test"},
    )

    assert set(report.loaded_provider_ids) == {"mock", "openrouter"}
    assert report.failures == ()
    assert registry.get("mock") is not None
    assert registry.get("openrouter") is not None


def test_provider_loader_collects_invalid_manifest_failures(tmp_path: Path) -> None:
    invalid_manifest_path = tmp_path / "bad" / "manifest.json"
    invalid_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    invalid_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "type": "provider",
                "name": "broken",
                "version": "0.1.0",
                "entrypoint": "bad-entrypoint",
                "capabilities": {"chat_completion": True},
                "compatibility": {},
            }
        ),
        encoding="utf-8",
    )

    registry = ProviderRegistry()
    loader = ProviderLoader(registry)

    report = loader.load_from_paths(search_paths=[tmp_path], context={})

    assert report.loaded_provider_ids == ()
    assert len(report.failures) == 1
    assert report.failures[0].code == "provider.loader.invalid_entrypoint"


def test_provider_loader_skips_missing_paths() -> None:
    registry = ProviderRegistry()
    loader = ProviderLoader(registry)

    report = loader.load_from_paths(search_paths=[Path("does-not-exist")], context={})

    assert report.loaded_provider_ids == ()
    assert report.failures == ()
