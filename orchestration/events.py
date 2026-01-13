"""Orchestration events - Event, EventMetadata."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class EventMetadata:
    """Metadata for an event."""

    execution_id: str
    service: str
    operation: str | None
    timestamp: datetime


@dataclass
class Event:
    """Domain event in the orchestration system."""

    name: str
    payload: dict[str, object]
    metadata: EventMetadata
