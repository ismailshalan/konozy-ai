"""Tests for EventBus."""

from datetime import datetime, timezone

import pytest

from orchestration.bus import InMemoryEventBus
from orchestration.events import Event, EventMetadata


@pytest.mark.asyncio
async def test_event_bus_subscribe_and_publish():
    """Test subscribing and publishing events."""
    bus = InMemoryEventBus()

    events_received: list[Event] = []

    async def handler(event: Event) -> None:
        events_received.append(event)

    # Subscribe handler
    bus.subscribe("workflow.started", handler)

    # Create and publish event
    metadata = EventMetadata(
        execution_id="exec-test-123",
        service="test",
        operation="test_op",
        timestamp=datetime.now(timezone.utc),
    )
    event = Event(
        name="workflow.started",
        payload={"workflow_name": "test_workflow"},
        metadata=metadata,
    )

    await bus.publish(event)

    # Verify handler was called
    assert len(events_received) == 1
    assert events_received[0].name == "workflow.started"
    assert events_received[0].payload == {"workflow_name": "test_workflow"}
    assert events_received[0].metadata.execution_id == "exec-test-123"
    assert events_received[0].metadata.service == "test"


@pytest.mark.asyncio
async def test_event_bus_multiple_handlers():
    """Test multiple handlers for the same event."""
    bus = InMemoryEventBus()

    events_1: list[Event] = []
    events_2: list[Event] = []

    async def handler1(event: Event) -> None:
        events_1.append(event)

    async def handler2(event: Event) -> None:
        events_2.append(event)

    # Subscribe both handlers
    bus.subscribe("workflow.started", handler1)
    bus.subscribe("workflow.started", handler2)

    # Publish event
    metadata = EventMetadata(
        execution_id="exec-test-123",
        service="test",
        operation="test_op",
        timestamp=datetime.now(timezone.utc),
    )
    event = Event(
        name="workflow.started",
        payload={"workflow_name": "test_workflow"},
        metadata=metadata,
    )

    await bus.publish(event)

    # Verify both handlers were called
    assert len(events_1) == 1
    assert len(events_2) == 1
    assert events_1[0].name == "workflow.started"
    assert events_2[0].name == "workflow.started"


@pytest.mark.asyncio
async def test_event_bus_no_handlers():
    """Test publishing event with no handlers."""
    bus = InMemoryEventBus()

    metadata = EventMetadata(
        execution_id="exec-test-123",
        service="test",
        operation="test_op",
        timestamp=datetime.now(timezone.utc),
    )
    event = Event(
        name="workflow.started",
        payload={"workflow_name": "test_workflow"},
        metadata=metadata,
    )

    # Should not raise an error
    await bus.publish(event)
