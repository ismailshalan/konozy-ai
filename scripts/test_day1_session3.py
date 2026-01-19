"""Test Day 1 Session 3: Order Entity Integration with Event Store."""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.database.config import (
    init_database,
    get_session,
    close_database
)
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.event_bus import get_event_bus
from core.domain.entities.order import Order
from core.domain.entities.order_rebuilder import OrderEventRebuilder
from core.domain.value_objects import OrderNumber, ExecutionID, Money
from core.domain.events import OrderCreatedEvent, OrderStatusChangedEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_order_event_integration():
    """Test Order entity integration with Event Store."""
    
    logger.info("="*70)
    logger.info("DAY 1 - SESSION 3: Order Entity + Event Store Integration")
    logger.info("="*70)
    
    try:
        # 1. Initialize database
        logger.info("\n1. Initializing database...")
        await init_database()
        logger.info("✅ Database initialized")
        
        # 2. Create Order (publishes OrderCreatedEvent)
        logger.info("\n2. Creating Order (should publish OrderCreatedEvent)...")
        
        execution_id = ExecutionID("exec-session3-001")
        order = Order.create(
            order_id=OrderNumber("ORDER-S3-001"),
            purchase_date=datetime.utcnow(),
            buyer_email="test@example.com",
            marketplace="amazon",
            execution_id=execution_id,
        )
        
        domain_events = order.get_domain_events()
        logger.info(f"✅ Order created with {len(domain_events)} domain events")
        
        assert len(domain_events) == 1
        assert isinstance(domain_events[0], OrderCreatedEvent)
        assert domain_events[0].order_id == "ORDER-S3-001"
        logger.info(f"   Event: {domain_events[0].event_type}")
        
        # 3. Publish events through Event Bus (stores in Event Store)
        logger.info("\n3. Publishing events through Event Bus...")
        
        event_bus = get_event_bus()
        await event_bus.publish_all(domain_events)
        
        # Clear events from aggregate
        order.clear_domain_events()
        assert len(order.get_domain_events()) == 0
        logger.info("✅ Events published and cleared from aggregate")
        
        # 4. Change Order status (publishes OrderStatusChangedEvent)
        logger.info("\n4. Changing Order status (should publish OrderStatusChangedEvent)...")
        
        order.mark_synced()
        status_events = order.get_domain_events()
        
        logger.info(f"✅ Status changed with {len(status_events)} domain events")
        assert len(status_events) == 1
        assert isinstance(status_events[0], OrderStatusChangedEvent)
        assert status_events[0].previous_status == "Pending"
        assert status_events[0].new_status == "Synced"
        logger.info(f"   Event: {status_events[0].event_type} ({status_events[0].previous_status} -> {status_events[0].new_status})")
        
        # Publish status change event
        await event_bus.publish_all(status_events)
        order.clear_domain_events()
        logger.info("✅ Status change event published")
        
        # 5. Retrieve events from Event Store
        logger.info("\n5. Retrieving events from Event Store...")
        
        async for session in get_session():
            event_store = EventStore(session)
            retrieved_events = await event_store.get_events("ORDER-S3-001")
            break  # Exit after first iteration
        
        logger.info(f"✅ Retrieved {len(retrieved_events)} events from Event Store")
        
        assert len(retrieved_events) == 2
        assert retrieved_events[0].event_type == "OrderCreatedEvent"
        assert retrieved_events[1].event_type == "OrderStatusChangedEvent"
        
        # Display event stream
        logger.info("\n6. Event Stream:")
        for i, event in enumerate(retrieved_events, 1):
            logger.info(f"   {i}. {event.event_type} - {event.occurred_at}")
            if isinstance(event, OrderStatusChangedEvent):
                logger.info(f"      Status: {event.previous_status} -> {event.new_status}")
        
        # 7. Rebuild Order from events (Event Sourcing)
        logger.info("\n7. Rebuilding Order from events (Event Sourcing)...")
        
        rebuilt_order = OrderEventRebuilder.rebuild(retrieved_events)
        
        assert rebuilt_order is not None
        assert rebuilt_order.order_id.value == "ORDER-S3-001"
        assert rebuilt_order.order_status == "Synced"
        assert rebuilt_order.marketplace == "amazon"
        assert rebuilt_order.buyer_email == "test@example.com"
        
        logger.info("✅ Order rebuilt successfully from events")
        logger.info(f"   Order ID: {rebuilt_order.order_id.value}")
        logger.info(f"   Status: {rebuilt_order.order_status}")
        logger.info(f"   Marketplace: {rebuilt_order.marketplace}")
        
        logger.info("\n" + "="*70)
        logger.info("✅ DAY 1 - SESSION 3 COMPLETE!")
        logger.info("="*70)
        logger.info("\nOrder Entity Integration with Event Store:")
        logger.info("  ✅ Order aggregate root collects events")
        logger.info("  ✅ Events published through Event Bus")
        logger.info("  ✅ Events stored in Event Store")
        logger.info("  ✅ Order state rebuilt from events (Event Sourcing)")
        logger.info("  ✅ OrderCreated / OrderStatusChanged events working")
        
        logger.info("\n🎉 Session 3 Complete - Event Sourcing Pattern Implemented!")
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        raise
    
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(test_order_event_integration())
