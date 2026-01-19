"""
Snapshot Frequency Strategy.

Determines when to create snapshots for Event Sourcing optimization.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from core.infrastructure.database.event_store import EventStore


logger = logging.getLogger(__name__)


class SnapshotStrategy:
    """
    Strategy for determining when to create snapshots.
    
    Strategies:
    - EventCountStrategy: Create snapshot every N events
    - TimeBasedStrategy: Create snapshot after time interval
    - HybridStrategy: Combine event count and time-based
    """
    
    def should_create_snapshot(
        self,
        aggregate_id: str,
        current_sequence: int,
        event_store: EventStore
    ) -> bool:
        """
        Determine if snapshot should be created.
        
        Args:
            aggregate_id: Aggregate identifier
            current_sequence: Current event sequence number
            event_store: Event store instance (for querying)
        
        Returns:
            True if snapshot should be created, False otherwise
        """
        raise NotImplementedError


class EventCountSnapshotStrategy(SnapshotStrategy):
    """
    Create snapshot every N events.
    
    Example: Create snapshot every 10 events
    - After 10 events: snapshot at sequence 10
    - After 20 events: snapshot at sequence 20
    - etc.
    """
    
    def __init__(self, event_interval: int = 10):
        """
        Initialize event count strategy.
        
        Args:
            event_interval: Create snapshot every N events (default: 10)
        """
        self.event_interval = event_interval
        logger.info(f"EventCountSnapshotStrategy: snapshot every {event_interval} events")
    
    async def should_create_snapshot(
        self,
        aggregate_id: str,
        current_sequence: int,
        event_store: EventStore
    ) -> bool:
        """
        Check if snapshot should be created based on event count.
        
        Args:
            aggregate_id: Aggregate identifier
            current_sequence: Current event sequence number
            event_store: Event store instance
        
        Returns:
            True if current_sequence is multiple of event_interval
        """
        should_create = current_sequence > 0 and current_sequence % self.event_interval == 0
        
        if should_create:
            logger.debug(
                f"Snapshot trigger: {aggregate_id} reached {current_sequence} events "
                f"(interval: {self.event_interval})"
            )
        
        return should_create


class TimeBasedSnapshotStrategy(SnapshotStrategy):
    """
    Create snapshot after time interval.
    
    Example: Create snapshot if last snapshot is older than 1 hour
    """
    
    def __init__(self, time_interval_minutes: int = 60):
        """
        Initialize time-based strategy.
        
        Args:
            time_interval_minutes: Create snapshot if last snapshot is older than this (default: 60)
        """
        self.time_interval = timedelta(minutes=time_interval_minutes)
        logger.info(f"TimeBasedSnapshotStrategy: snapshot every {time_interval_minutes} minutes")
    
    async def should_create_snapshot(
        self,
        aggregate_id: str,
        current_sequence: int,
        event_store: EventStore
    ) -> bool:
        """
        Check if snapshot should be created based on time.
        
        Args:
            aggregate_id: Aggregate identifier
            current_sequence: Current event sequence number
            event_store: Event store instance
        
        Returns:
            True if last snapshot is older than time_interval
        """
        from core.infrastructure.database.snapshot_store import SnapshotStore
        from core.infrastructure.database.config import get_session
        
        # Get last snapshot
        async for session in get_session():
            snapshot_store = SnapshotStore(session)
            last_snapshot = await snapshot_store.get_latest_snapshot(aggregate_id)
            break
        
        if not last_snapshot:
            # No snapshot exists - create first one
            logger.debug(f"Snapshot trigger: {aggregate_id} has no snapshot (first snapshot)")
            return True
        
        # Check if last snapshot is older than interval
        time_since_snapshot = datetime.utcnow() - last_snapshot.created_at
        should_create = time_since_snapshot > self.time_interval
        
        if should_create:
            logger.debug(
                f"Snapshot trigger: {aggregate_id} last snapshot is "
                f"{time_since_snapshot.total_seconds() / 60:.1f} minutes old "
                f"(interval: {self.time_interval.total_seconds() / 60:.1f} minutes)"
            )
        
        return should_create


class HybridSnapshotStrategy(SnapshotStrategy):
    """
    Combine event count and time-based strategies.
    
    Create snapshot if EITHER condition is met:
    - Event count threshold reached, OR
    - Time interval elapsed
    """
    
    def __init__(
        self,
        event_interval: int = 10,
        time_interval_minutes: int = 60
    ):
        """
        Initialize hybrid strategy.
        
        Args:
            event_interval: Create snapshot every N events
            time_interval_minutes: Create snapshot if last snapshot is older than this
        """
        self.event_strategy = EventCountSnapshotStrategy(event_interval)
        self.time_strategy = TimeBasedSnapshotStrategy(time_interval_minutes)
        logger.info(
            f"HybridSnapshotStrategy: snapshot every {event_interval} events "
            f"OR every {time_interval_minutes} minutes"
        )
    
    async def should_create_snapshot(
        self,
        aggregate_id: str,
        current_sequence: int,
        event_store: EventStore
    ) -> bool:
        """
        Check if snapshot should be created (either condition).
        
        Args:
            aggregate_id: Aggregate identifier
            current_sequence: Current event sequence number
            event_store: Event store instance
        
        Returns:
            True if event count OR time condition is met
        """
        event_trigger = await self.event_strategy.should_create_snapshot(
            aggregate_id, current_sequence, event_store
        )
        time_trigger = await self.time_strategy.should_create_snapshot(
            aggregate_id, current_sequence, event_store
        )
        
        return event_trigger or time_trigger


# Default strategy: Event count (every 10 events)
DEFAULT_SNAPSHOT_STRATEGY = EventCountSnapshotStrategy(event_interval=10)
