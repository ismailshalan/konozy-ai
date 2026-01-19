"""
Base Domain Event.

All domain events inherit from this base class.
Foundation for Event Sourcing and Event-driven Architecture.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


@dataclass
class DomainEvent:
    """
    Base class for all domain events.
    
    Events are immutable records of things that have happened.
    They capture state changes in the system.
    
    Architecture Note:
    - Part of 1.1 Event Bus (Orchestration Layer)
    - Foundation for multi-agent communication
    - Enables event-driven workflows
    """
    
    # Event metadata
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(init=False)
    event_version: int = 1
    
    # Aggregate information
    aggregate_id: str = field(default="")
    aggregate_type: str = field(init=False)
    
    # Execution context (1.3 Execution-ID Architecture)
    execution_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Timestamp
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Set event type and aggregate type from class name."""
        if not hasattr(self, 'event_type') or not self.event_type:
            object.__setattr__(self, 'event_type', self.__class__.__name__)
        
        if not hasattr(self, 'aggregate_type') or not self.aggregate_type:
            object.__setattr__(self, 'aggregate_type', self._get_aggregate_type())
    
    def _get_aggregate_type(self) -> str:
        """
        Extract aggregate type from event type.
        
        Example: OrderCreatedEvent -> Order
        """
        event_name = self.__class__.__name__
        
        # Remove 'Event' suffix
        if event_name.endswith('Event'):
            event_name = event_name[:-5]
        
        # Extract aggregate name (first word before action)
        for i, char in enumerate(event_name):
            if i > 0 and char.isupper():
                return event_name[:i]
        
        return event_name
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert event to dictionary for serialization.
        
        Used for:
        - Event Store persistence
        - Event Bus publishing
        - API responses
        
        Returns:
            Dictionary representation of event
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "occurred_at": self.occurred_at.isoformat(),
            "data": self._get_event_data()
        }
    
    def _get_event_data(self) -> Dict[str, Any]:
        """
        Get event-specific data.
        
        Override in subclasses to provide event payload.
        
        Returns:
            Event data dictionary
        """
        from decimal import Decimal
        
        data = {}
        
        for key, value in self.__dict__.items():
            if key not in [
                'event_id', 'event_type', 'event_version',
                'aggregate_id', 'aggregate_type',
                'execution_id', 'user_id', 'occurred_at'
            ]:
                # Serialize value
                if isinstance(value, Decimal):
                    # Convert Decimal to string for JSON serialization
                    data[key] = str(value)
                elif hasattr(value, 'to_dict'):
                    data[key] = value.to_dict()
                elif hasattr(value, '__dict__'):
                    data[key] = str(value)
                else:
                    data[key] = value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainEvent':
        """
        Create event from dictionary.
        
        Used for:
        - Event Store retrieval
        - Event Bus consumption
        - API requests
        
        Args:
            data: Event data dictionary
        
        Returns:
            Event instance
        """
        event_data = data.get('data', {})
        
        return cls(
            aggregate_id=data['aggregate_id'],
            execution_id=data.get('execution_id'),
            user_id=data.get('user_id'),
            **event_data
        )
