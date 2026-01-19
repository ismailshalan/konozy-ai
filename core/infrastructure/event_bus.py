"""
Event Bus Implementation (Infrastructure Layer).

Publishes events to Event Store and notifies subscribers.
"""
import logging
from typing import List, Set, Callable, Optional
from asyncio import Queue, Task
import asyncio

from core.domain.event_bus import EventBus
from core.domain.events.base import DomainEvent
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.database.config import get_session


logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    """
    In-Memory Event Bus Implementation.
    
    Features:
    - Publishes events to Event Store
    - Notifies registered subscribers
    - Supports async event handling
    - Part of 1.1 Event Bus (Orchestration Layer)
    
    Architecture:
    - Infrastructure layer (uses EventStore)
    - Can be replaced with message broker (RabbitMQ, Kafka)
    - Maintains event order per aggregate
    """
    
    def __init__(self):
        """Initialize event bus with subscribers."""
        self._subscribers: Set[Callable[[DomainEvent], None]] = set()
        self._event_queue: Optional[Queue] = None
        self._worker_task: Optional[Task] = None
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.
        
        Events are:
        1. Stored in Event Store
        2. Notified to all subscribers
        
        Args:
            event: Domain event to publish
        """
        logger.info(f"Publishing event: {event.event_type} (aggregate: {event.aggregate_id})")
        
        # Store event in Event Store
        async for session in get_session():
            event_store = EventStore(session)
            try:
                await event_store.append(event)
                await session.commit()
                logger.info(f"✅ Event stored: {event.event_type}")
            except Exception as e:
                logger.error(f"Failed to store event: {e}")
                await session.rollback()
                raise
            break  # Exit after first iteration
        
        # Notify subscribers
        await self._notify_subscribers(event)
    
    async def publish_all(self, events: List[DomainEvent]) -> None:
        """
        Publish multiple domain events atomically.
        
        All events are stored in a single transaction.
        
        Args:
            events: List of domain events to publish
        """
        if not events:
            return
        
        logger.info(f"Publishing {len(events)} events atomically")
        
        # Store all events in Event Store (single transaction)
        async for session in get_session():
            event_store = EventStore(session)
            try:
                for event in events:
                    await event_store.append(event)
                    logger.debug(f"Storing event: {event.event_type}")
                
                await session.commit()
                logger.info(f"✅ All {len(events)} events stored")
            except Exception as e:
                logger.error(f"Failed to store events: {e}")
                await session.rollback()
                raise
            break  # Exit after first iteration
        
        # Notify subscribers for all events
        for event in events:
            await self._notify_subscribers(event)
    
    def subscribe(self, handler: Callable[[DomainEvent], None]) -> None:
        """
        Subscribe to all domain events.
        
        Args:
            handler: Callback function that receives events
        """
        self._subscribers.add(handler)
        logger.info(f"Registered event subscriber: {handler.__name__}")
    
    def unsubscribe(self, handler: Callable[[DomainEvent], None]) -> None:
        """
        Unsubscribe from domain events.
        
        Args:
            handler: Callback function to remove
        """
        self._subscribers.discard(handler)
        logger.info(f"Unregistered event subscriber: {handler.__name__}")
    
    async def _notify_subscribers(self, event: DomainEvent) -> None:
        """Notify all subscribers about an event."""
        if not self._subscribers:
            return
        
        logger.debug(f"Notifying {len(self._subscribers)} subscribers about {event.event_type}")
        
        for subscriber in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Subscriber {subscriber.__name__} failed: {e}", exc_info=True)


# Global event bus instance
_event_bus_instance: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    """
    Get or create global event bus instance.
    
    Returns:
        Global event bus instance
    """
    global _event_bus_instance
    
    if _event_bus_instance is None:
        _event_bus_instance = InMemoryEventBus()
    
    return _event_bus_instance
