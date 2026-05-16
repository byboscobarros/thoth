"""Provider selection strategy based on capability, preference and health."""

from __future__ import annotations

from dataclasses import dataclass

from thoth.core.provider_registry import ProviderRegistry, RegisteredProvider
from thoth.domain.providers import ProviderExecutionError


@dataclass(slots=True, frozen=True)
class ProviderSelectionConfig:
    """Configuration values controlling deterministic provider selection."""

    preferred_provider: str | None = None
    require_healthy: bool = True


class ProviderSelector:
    """Select providers by required capability with optional preferred fallback."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def select(
        self,
        *,
        capability: str,
        config: ProviderSelectionConfig | None = None,
    ) -> RegisteredProvider:
        effective_config = config or ProviderSelectionConfig()
        candidates = self._registry.list_by_capability(capability)

        if effective_config.preferred_provider:
            preferred = self._registry.get(effective_config.preferred_provider)
            if (
                preferred is not None
                and self._supports_capability(preferred, capability)
                and self._is_eligible(preferred, require_healthy=effective_config.require_healthy)
            ):
                return preferred

        for candidate in candidates:
            if self._is_eligible(candidate, require_healthy=effective_config.require_healthy):
                return candidate

        raise ProviderExecutionError(
            code="provider.selection.unavailable",
            message=(
                f"no provider available for capability '{capability}' "
                f"(require_healthy={effective_config.require_healthy})"
            ),
        )

    @staticmethod
    def _supports_capability(entry: RegisteredProvider, capability: str) -> bool:
        return entry.manifest.capabilities.get(capability, False)

    @staticmethod
    def _is_eligible(entry: RegisteredProvider, *, require_healthy: bool) -> bool:
        if not require_healthy:
            return True
        return entry.health.ok
