"""Manifest-driven provider discovery and loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any

from thoth.core.provider_registry import ProviderRegistry
from thoth.domain.provider_manifest import load_provider_manifest
from thoth.domain.providers import Provider, ProviderConfigurationError


@dataclass(slots=True, frozen=True)
class ProviderLoadFailure:
    """Structured provider loading failure entry."""

    manifest_path: str
    code: str
    message: str


@dataclass(slots=True, frozen=True)
class ProviderLoadReport:
    """Summary of loaded providers and failures."""

    loaded_provider_ids: tuple[str, ...] = field(default_factory=tuple)
    failures: tuple[ProviderLoadFailure, ...] = field(default_factory=tuple)


class ProviderLoader:
    """Load providers from manifest files into a registry."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def discover_manifests(self, search_paths: list[Path]) -> list[Path]:
        manifests: list[Path] = []
        for search_path in search_paths:
            if not search_path.exists():
                continue
            manifests.extend(sorted(search_path.rglob("manifest.json")))
        return manifests

    def load_from_paths(
        self,
        *,
        search_paths: list[Path],
        context: dict[str, Any] | None = None,
    ) -> ProviderLoadReport:
        runtime_context = dict(context or {})
        loaded: list[str] = []
        failures: list[ProviderLoadFailure] = []

        for manifest_path in self.discover_manifests(search_paths):
            try:
                manifest = load_provider_manifest(manifest_path)
                provider_class = _import_entrypoint(manifest.entrypoint)
                provider = provider_class()
                provider.initialize(runtime_context)
                provider_id = manifest.name
                self._registry.register(provider_id=provider_id, provider=provider, manifest=manifest)
                loaded.append(provider_id)
            except (ProviderConfigurationError, ValueError, AttributeError, TypeError) as exc:
                failures.append(
                    ProviderLoadFailure(
                        manifest_path=str(manifest_path),
                        code=_resolve_error_code(exc),
                        message=str(exc),
                    )
                )

        return ProviderLoadReport(
            loaded_provider_ids=tuple(loaded),
            failures=tuple(failures),
        )


def _import_entrypoint(entrypoint: str) -> type[Provider]:
    try:
        module_name, symbol_name = entrypoint.split(":", maxsplit=1)
    except ValueError as exc:
        raise ProviderConfigurationError(
            code="provider.loader.invalid_entrypoint",
            message=f"invalid entrypoint format: {entrypoint}",
        ) from exc

    module = import_module(module_name)
    symbol = getattr(module, symbol_name)
    if not isinstance(symbol, type):
        raise ProviderConfigurationError(
            code="provider.loader.invalid_entrypoint",
            message=f"entrypoint is not a class: {entrypoint}",
        )
    return symbol


def _resolve_error_code(exc: Exception) -> str:
    if isinstance(exc, ProviderConfigurationError):
        return exc.code
    return "provider.loader.failed"
