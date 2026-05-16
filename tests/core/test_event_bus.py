from thoth.core.event_bus import InMemoryEventBus
from thoth.domain.events import RuntimeEvent, RuntimeEventType


def test_publish_records_event_and_notifies_subscriber() -> None:
    event_bus = InMemoryEventBus()
    observed: list[RuntimeEvent] = []
    event_bus.subscribe(observed.append)

    event = RuntimeEvent(
        type=RuntimeEventType.REQUEST_RECEIVED,
        request_id="req_1",
        session_id="sess_1",
    )
    event_bus.publish(event)

    assert event_bus.published_events == (event,)
    assert observed == [event]
