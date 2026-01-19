"""
Event Store Implementation.

Append-only storage for domain events using PostgreSQL.

Architecture:
- Part of 1.1 Event Bus
- Foundation for Event Sourcing
- Enables time-travel debugging
- Compliance-ready audit trail
"""
import logging
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
import uuid

from core.domain.events.base import DomainEvent
from core.infrastructure.database.models import EventModel


logger = logging.getLogger(__name__)


class ConcurrencyError(Exception):
    """Raised when concurrent modification detected."""
    pass


class EventStore:
    """
    Event Store for domain events.
    
    Features:
    - Append-only (events never modified or deleted)
    - Optimistic concurrency control (sequence numbers)
    - Event versioning
    - Time-travel queries
    - Aggregate rebuilding
    
    Usage:
        async with get_session() as session:
            event_store = EventStore(session)
            await event_store.append(event)
            events = await event_store.get_events("order-123")
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize event store.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def append(
        self,
        event: DomainEvent,
        expected_version: Optional[int] = None
    ) -> None:
        """
        Append event to store.
        
        This is append-only. Events are immutable once written.
        
        Args:
            event: Domain event to append
            expected_version: Expected sequence number (optimistic locking)
        
        Raises:
            ConcurrencyError: If expected_version doesn't match
        """
        logger.info(
            f"Appending event: {event.event_type} "
            f"(aggregate: {event.aggregate_id})"
        )
        
        # Get next sequence number
        sequence_number = await self._get_next_sequence_number(
            event.aggregate_id
        )
        
        # Check optimistic concurrency
        if expected_version is not None:
            if sequence_number != expected_version:
                raise ConcurrencyError(
                    f"Concurrency conflict: expected {expected_version}, "
                    f"but current is {sequence_number - 1}"
                )
        
        # Build metadata
        metadata = self._build_metadata(event)
        
        # Create event model
        event_model = EventModel(
            event_id=uuid.UUID(event.event_id),
            event_type=event.event_type,
            event_version=event.event_version,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            event_data=event._get_event_data(),
            execution_id=uuid.UUID(event.execution_id) if event.execution_id else None,
            user_id=event.user_id,
            occurred_at=event.occurred_at,
            sequence_number=sequence_number,
            metadata=metadata,
        )
        
        try:
            # Add to session
            self.session.add(event_model)
            await self.session.flush()
            
            logger.info(
                f"✅ Event appended: {event.event_type} "
                f"(sequence: {sequence_number})"
            )
        
        except IntegrityError as e:
            logger.error(f"Failed to append: {e}")
            raise ConcurrencyError(
                "Event append failed - concurrent modification detected"
            )
    
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None
    ) -> List[DomainEvent]:
        """
        Get all events for an aggregate.
        
        Args:
            aggregate_id: Aggregate ID
            from_sequence: Start from this sequence (inclusive)
            to_sequence: End at this sequence (inclusive)
        
        Returns:
            List of domain events in order
        """
        logger.info(f"Loading events for: {aggregate_id}")
        
        # Build query
        query = select(EventModel).where(
            EventModel.aggregate_id == aggregate_id
        )
        
        if from_sequence > 0:
            query = query.where(
                EventModel.sequence_number >= from_sequence
            )
        
        if to_sequence is not None:
            query = query.where(
                EventModel.sequence_number <= to_sequence
            )
        
        # Order by sequence
        query = query.order_by(EventModel.sequence_number)
        
        # Execute
        result = await self.session.execute(query)
        event_models = result.scalars().all()
        
        # Convert to domain events
        events = []
        for model in event_models:
            domain_event = self._to_domain_event(model)
            if domain_event:
                events.append(domain_event)
        
        logger.info(f"✅ Loaded {len(events)} events")
        
        return events
    
    async def get_latest_sequence(
        self,
        aggregate_id: str
    ) -> int:
        """
        Get latest sequence number for aggregate.
        
        Args:
            aggregate_id: Aggregate ID
        
        Returns:
            Latest sequence number (0 if no events)
        """
        query = select(
            func.max(EventModel.sequence_number)
        ).where(
            EventModel.aggregate_id == aggregate_id
        )
        
        result = await self.session.execute(query)
        max_seq = result.scalar()
        
        return max_seq or 0
    
    async def get_events_by_execution(
        self,
        execution_id: str
    ) -> List[DomainEvent]:
        """
        Get all events for an execution.
        
        Used for workflow tracing and debugging.
        
        Args:
            execution_id: Execution ID
        
        Returns:
            List of domain events ordered by occurred_at
        """
        logger.info(f"Loading events for execution: {execution_id}")
        
        query = select(EventModel).where(
            EventModel.execution_id == uuid.UUID(execution_id)
        ).order_by(EventModel.occurred_at)
        
        result = await self.session.execute(query)
        event_models = result.scalars().all()
        
        # Convert to domain events
        events = []
        for model in event_models:
            domain_event = self._to_domain_event(model)
            if domain_event:
                events.append(domain_event)
        
        logger.info(f"✅ Loaded {len(events)} events for execution")
        
        return events
    
    async def aggregate_exists(
        self,
        aggregate_id: str
    ) -> bool:
        """
        Check if aggregate has any events.
        
        Args:
            aggregate_id: Aggregate ID
        
        Returns:
            True if aggregate exists, False otherwise
        """
        query = select(func.count(EventModel.id)).where(
            EventModel.aggregate_id == aggregate_id
        )
        
        result = await self.session.execute(query)
        count = result.scalar()
        
        return count > 0
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    async def _get_next_sequence_number(
        self,
        aggregate_id: str
    ) -> int:
        """Get next sequence number for aggregate."""
        current = await self.get_latest_sequence(aggregate_id)
        return current + 1
    
    def _to_domain_event(self, model: EventModel) -> Optional[DomainEvent]:
        """Convert EventModel to DomainEvent."""
        # Import event classes
        from core.domain.events import (
            OrderCreatedEvent,
            OrderUpdatedEvent,
            OrderStatusChangedEvent,
            FinancialsExtractedEvent,
            OrderValidatedEvent,
            OrderSavedEvent,
            InvoiceCreatedEvent,
            OrderSyncedEvent,
            OrderFailedEvent,
            NotificationSentEvent,
        )
        
        # Map event type to class
        event_classes = {
            'OrderCreatedEvent': OrderCreatedEvent,
            'OrderUpdatedEvent': OrderUpdatedEvent,
            'OrderStatusChangedEvent': OrderStatusChangedEvent,
            'FinancialsExtractedEvent': FinancialsExtractedEvent,
            'OrderValidatedEvent': OrderValidatedEvent,
            'OrderSavedEvent': OrderSavedEvent,
            'InvoiceCreatedEvent': InvoiceCreatedEvent,
            'OrderSyncedEvent': OrderSyncedEvent,
            'OrderFailedEvent': OrderFailedEvent,
            'NotificationSentEvent': NotificationSentEvent,
        }
        
        event_class = event_classes.get(model.event_type)
        
        if not event_class:
            logger.warning(f"Unknown event type: {model.event_type}")
            return None
        
        # Reconstruct event data (convert Decimal strings back to Decimal)
        from decimal import Decimal, InvalidOperation
        
        # Fields that should be Decimal
        decimal_fields = {'principal_amount', 'net_proceeds', 'amount', 'principal', 'net'}
        
        event_data = {}
        for key, value in model.event_data.items():
            # Convert string numbers back to Decimal for financial fields
            if isinstance(value, str) and key in decimal_fields:
                try:
                    event_data[key] = Decimal(value)
                except (ValueError, InvalidOperation, TypeError):
                    # If conversion fails, keep as string
                    event_data[key] = value
            else:
                event_data[key] = value
        
        # Reconstruct event
        event = event_class(
            aggregate_id=model.aggregate_id,
            execution_id=str(model.execution_id) if model.execution_id else None,
            user_id=model.user_id,
            **event_data
        )
        
        # Set metadata
        object.__setattr__(event, 'event_id', str(model.event_id))
        object.__setattr__(event, 'occurred_at', model.occurred_at)
        
        return event
    
    def _build_metadata(self, event: DomainEvent) -> dict:
        """
        Build metadata dictionary for event.
        
        Args:
            event: Domain event
        
        Returns:
            Metadata dictionary with event_class and event_module
        """
        return {
            'event_class': event.__class__.__name__,
            'event_module': event.__class__.__module__,
        }