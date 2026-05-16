"""In-process event bus for runtime domain events."""

from __future__ import annotations

from collections.abc import Callable

from thoth.domain.events import RuntimeEvent


class EventBus:
    """Minimal event bus contract for publishing runtime events."""

    def publish(self, event: RuntimeEvent) -> None:
        """Publish a runtime event."""


class InMemoryEventBus(EventBus):
    """In-memory event bus with optional subscribers for local runtime use."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []
        self._published_events: list[RuntimeEvent] = []

    def subscribe(self, subscriber: Callable[[RuntimeEvent], None]) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: RuntimeEvent) -> None:
        self._published_events.append(event)
        for subscriber in self._subscribers:
            subscriber(event)

    @property
    def published_events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(self._published_events)
