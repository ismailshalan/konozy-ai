"""Event bus - EventBusProtocol and InMemoryEventBus."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from konozy_sdk.logging import get_logger

from .events import Event

EventHandler = Callable[[Event], Awaitable[None]]


class EventBusProtocol(Protocol):
    """Protocol for event bus implementations."""

    async def publish(self, event: Event) -> None:
        """Publish an event.

        Args:
            event: Event to publish
        """
        ...

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event name.

        Args:
            event_name: Event name to subscribe to
            handler: Async handler function
        """
        ...


class InMemoryEventBus(EventBusProtocol):
    """In-memory event bus implementation."""

    def __init__(self) -> None:
        """Initialize in-memory event bus."""
        self._handlers: dict[str, list[EventHandler]] = {}
        self._logger = get_logger("orchestration.event_bus")

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event name.

        Args:
            event_name: Event name to subscribe to
            handler: Async handler function
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers.

        Args:
            event: Event to publish
        """
        handlers = self._handlers.get(event.name, [])
        if not handlers:
            return

        self._logger.info(
            "publishing_event",
            event_name=event.name,
            execution_id=event.metadata.execution_id,
            handler_count=len(handlers),
        )

        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                self._logger.error(
                    "handler_error",
                    event_name=event.name,
                    handler=str(handler),
                    error=str(exc),
                    exc_info=True,
                )
