"""Capability components for the mock provider."""

from thoth.providers.mock.components.completion import MockCompletionComponent
from thoth.providers.mock.components.streaming import MockStreamingComponent

__all__ = ["MockCompletionComponent", "MockStreamingComponent"]
