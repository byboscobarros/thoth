"""Provider registry and capability lookup index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from thoth.domain.provider_manifest import ProviderManifest
from thoth.domain.providers import Provider, ProviderHealth


@dataclass(slots=True)
class RegisteredProvider:
    """Provider entry tracked by the registry."""

    provider_id: str
    provider: Provider
    manifest: ProviderManifest
    health: ProviderHealth
    registered_at: datetime


class ProviderRegistry:
    """In-memory provider registry indexed by id, capability and health."""

    def __init__(self) -> None:
        self._providers: dict[str, RegisteredProvider] = {}
        self._capability_index: dict[str, set[str]] = {}
        self._health_index: dict[bool, set[str]] = {True: set(), False: set()}

    def register(self, *, provider_id: str, provider: Provider, manifest: ProviderManifest) -> None:
        if provider_id in self._providers:
            raise ValueError(f"provider already registered: {provider_id}")

        health = provider.healthcheck()
        entry = RegisteredProvider(
            provider_id=provider_id,
            provider=provider,
            manifest=manifest,
            health=health,
            registered_at=datetime.now(UTC),
        )
        self._providers[provider_id] = entry

        for capability, enabled in manifest.capabilities.items():
            if enabled:
                bucket = self._capability_index.setdefault(capability, set())
                bucket.add(provider_id)

        self._health_index[health.ok].add(provider_id)

    def get(self, provider_id: str) -> RegisteredProvider | None:
        return self._providers.get(provider_id)

    def list(self) -> list[RegisteredProvider]:
        return [self._providers[provider_id] for provider_id in sorted(self._providers)]

    def list_by_capability(self, capability: str) -> list[RegisteredProvider]:
        provider_ids = sorted(self._capability_index.get(capability, set()))
        return [self._providers[provider_id] for provider_id in provider_ids]

    def list_by_health(self, ok: bool) -> list[RegisteredProvider]:
        provider_ids = sorted(self._health_index.get(ok, set()))
        return [self._providers[provider_id] for provider_id in provider_ids]

    def update_health(self, provider_id: str, health: ProviderHealth) -> None:
        entry = self._providers.get(provider_id)
        if entry is None:
            raise ValueError(f"provider not registered: {provider_id}")

        self._health_index[entry.health.ok].discard(provider_id)
        entry.health = health
        self._health_index[health.ok].add(provider_id)
