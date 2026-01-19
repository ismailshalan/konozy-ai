"""
Event Bus Interface (Domain Layer).

Pure interface definition - no implementation details.
"""
from abc import ABC, abstractmethod
from typing import List

from .events.base import DomainEvent


class EventBus(ABC):
    """
    Event Bus Interface.
    
    Part of 1.1 Event Bus (Orchestration Layer).
    Enables event-driven architecture and multi-agent communication.
    
    Architecture:
    - Domain interface (no implementation)
    - Implemented in infrastructure layer
    - Used by aggregates to publish events
    - Consumed by agents and services
    """
    
    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.
        
        Args:
            event: Domain event to publish
        """
        pass
    
    @abstractmethod
    async def publish_all(self, events: List[DomainEvent]) -> None:
        """
        Publish multiple domain events atomically.
        
        Args:
            events: List of domain events to publish
        """
        pass
