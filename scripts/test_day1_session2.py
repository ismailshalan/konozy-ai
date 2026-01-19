"""
Test Day 1 Session 2: Event Store Implementation.

Tests the Event Store for persistent event storage in PostgreSQL.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.database.config import (
    init_database,
    get_session,
    close_database
)
from core.infrastructure.database.event_store import EventStore
from core.domain.events import OrderCreatedEvent, OrderSyncedEvent


logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


async def test_event_store():
    """Test Event Store implementation."""
    
    print("=" * 70)
    print("DAY 1 - SESSION 2: Event Store Test")
    print("=" * 70)
    print()
    
    try:
        # 1. Initialize database
        print("1. Initializing database...")
        await init_database()
        print("✅ Database initialized")
        print()
        
        # 2. Create test events
        print("2. Creating test events...")
        
        execution_id = str(uuid4())
        aggregate_id = "ES-TEST-001"
        
        event1 = OrderCreatedEvent(
            aggregate_id=aggregate_id,
            execution_id=execution_id,
            order_id=aggregate_id,
            marketplace="amazon",
            buyer_email="test@example.com",
            purchase_date=datetime.utcnow().isoformat()
        )
        
        event2 = OrderSyncedEvent(
            aggregate_id=aggregate_id,
            execution_id=execution_id,
            order_id=aggregate_id,
            invoice_id=12345,
            principal_amount=None,
            net_proceeds=None
        )
        
        events = [event1, event2]
        print(f"✅ Created {len(events)} test events")
        print()
        
        # 3. Persist events to event store
        print("3. Persisting events to event store...")
        
        async for session in get_session():
            event_store = EventStore(session)
            
            # Append first event
            await event_store.append(event1)
            print(f"✅ Event appended: {event1.event_type} (sequence: 1)")
            
            # Append second event
            await event_store.append(event2)
            print(f"✅ Event appended: {event2.event_type} (sequence: 2)")
            
            # Commit transaction
            await session.commit()
            break  # Exit after first iteration
        
        print("✅ Events persisted")
        print()
        
        # 4. Retrieve events
        print("4. Retrieving events...")
        
        async for session in get_session():
            event_store = EventStore(session)
            retrieved_events = await event_store.get_events(aggregate_id)
            break  # Exit after first iteration
        
        print(f"✅ Loaded {len(retrieved_events)} events")
        print()
        
        # 5. Display event stream
        print("5. Event Stream:")
        for i, event in enumerate(retrieved_events, 1):
            event_time = event.occurred_at.strftime("%H:%M:%S")
            print(f"   {i}. {event.event_type} at {event_time}")
        print()
        
        # 6. Test execution query
        print("6. Testing execution query...")
        
        async for session in get_session():
            event_store = EventStore(session)
            execution_events = await event_store.get_events_by_execution(execution_id)
            break  # Exit after first iteration
        
        print(f"✅ Found {len(execution_events)} events for execution")
        print()
        
        # 7. Verify sequence numbers
        print("7. Verifying sequence numbers...")
        
        async for session in get_session():
            event_store = EventStore(session)
            
            # Check latest sequence
            latest_seq = await event_store.get_latest_sequence(aggregate_id)
            assert latest_seq == 2, f"Expected latest sequence 2, got {latest_seq}"
            
            # Check aggregate exists
            exists = await event_store.aggregate_exists(aggregate_id)
            assert exists, "Aggregate should exist"
            
            # Verify sequence order
            assert len(retrieved_events) == 2, "Should have 2 events"
            assert retrieved_events[0].event_type == "OrderCreatedEvent", "First event should be OrderCreatedEvent"
            assert retrieved_events[1].event_type == "OrderSyncedEvent", "Second event should be OrderSyncedEvent"
            
            break  # Exit after first iteration
        
        print("✅ Sequence order correct")
        print()
        
        print("=" * 70)
        print("✅ DAY 1 - SESSION 2 COMPLETE!")
        print("=" * 70)
        print()
        
        print("Event Store is working:")
        print("  ✅ Events appended")
        print("  ✅ Events retrieved")
        print("  ✅ Execution tracking")
        print("  ✅ Sequence numbers")
        print()
        print("Ready for Session 3: Order Entity Integration")
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        raise
    
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(test_event_store())
