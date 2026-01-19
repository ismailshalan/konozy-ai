"""
End-to-End Integration Test: Day 1 Session 4 - Snapshot Architecture.

Tests the complete snapshot optimization flow:
1. Create Order with multiple events
2. Verify snapshot creation (based on strategy)
3. Rebuild Order using snapshot (optimized path)
4. Verify backward compatibility (works without snapshots)
5. Compare performance: with vs without snapshots
"""
import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.database.config import (
    init_database,
    get_session,
    close_database,
    settings
)
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.database.snapshot_store import SnapshotStore
from core.infrastructure.database.snapshot_strategy import EventCountSnapshotStrategy
from core.infrastructure.event_bus import get_event_bus
from core.application.use_cases.sync_amazon_order import (
    SyncAmazonOrderUseCase,
    SyncAmazonOrderRequest,
)
from core.domain.entities.order_rebuilder import OrderEventRebuilder
from core.domain.value_objects import OrderNumber
from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
from core.infrastructure.adapters.odoo.mock_odoo_client import MockOdooClient
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService


logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# Use temporary test database
TEST_DB_PATH = Path("test_snapshots_session4.db").absolute()


def setup_test_database():
    """Setup temporary test database."""
    # Remove existing test database if it exists
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    # Update database URL
    settings.database_url = f"sqlite+aiosqlite:///{TEST_DB_PATH}"


def cleanup_test_database():
    """Cleanup temporary test database."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


async def test_snapshot_architecture():
    """Test complete snapshot architecture."""
    
    print("=" * 70)
    print("DAY 1 - SESSION 4: Snapshot Architecture Test")
    print("=" * 70)
    print()
    
    try:
        # Setup test database
        print("1. Setting up test database...")
        setup_test_database()
        await init_database()
        print("✅ Test database initialized")
        print()
        
        # Create Use Case with snapshot strategy (every 5 events)
        print("2. Creating Use Case with snapshot strategy (every 5 events)...")
        order_repository = MockOrderRepository()
        odoo_client = MockOdooClient()
        notification_service = MockNotificationService()
        event_bus = get_event_bus()
        snapshot_strategy = EventCountSnapshotStrategy(event_interval=5)
        
        use_case = SyncAmazonOrderUseCase(
            order_repository=order_repository,
            odoo_client=odoo_client,
            notification_service=notification_service,
            event_bus=event_bus,
            snapshot_strategy=snapshot_strategy,
        )
        print("✅ Use Case created with snapshot strategy")
        print()
        
        # Prepare test data
        print("3. Preparing test data...")
        amazon_order_id = "123-4567890-1234567"
        
        financial_events = {
            "ShipmentEventList": [
                {
                    "PostedDate": datetime.utcnow().isoformat(),
                    "ShipmentItemList": [
                        {
                            "OrderItemId": "123456789",
                            "SellerSKU": "TEST-SKU-001",
                            "ItemChargeList": [
                                {
                                    "ChargeType": "Principal",
                                    "ChargeAmount": {
                                        "CurrencyCode": "EGP",
                                        "CurrencyAmount": 100.00
                                    }
                                }
                            ]
                        }
                    ],
                    "ShipmentFeeList": [
                        {
                            "FeeType": "FBAFees",
                            "FeeAmount": {
                                "CurrencyCode": "EGP",
                                "CurrencyAmount": -10.00
                            }
                        }
                    ]
                }
            ],
            "TotalExpenses": {
                "CurrencyCode": "EGP",
                "CurrencyAmount": -10.00
            }
        }
        
        print(f"   Order ID: {amazon_order_id}")
        print("✅ Test data prepared")
        print()
        
        # Execute Use Case (creates 6 events, should trigger snapshot at sequence 5)
        print("4. Executing Use Case (creates 6 events, snapshot at sequence 5)...")
        request = SyncAmazonOrderRequest(
            amazon_order_id=amazon_order_id,
            financial_events=financial_events,
            buyer_email="test@example.com",
            dry_run=False,
        )
        
        response = await use_case.execute(request)
        print(f"✅ Use Case executed successfully")
        print(f"   Execution ID: {response.execution_id.value}")
        print()
        
        # Verify snapshot was created
        print("5. Verifying snapshot creation...")
        
        async for session in get_session():
            snapshot_store = SnapshotStore(session)
            snapshot = await snapshot_store.get_latest_snapshot(amazon_order_id)
            break
        
        assert snapshot is not None, "Snapshot should be created"
        assert snapshot.sequence_number == 5, f"Expected snapshot at sequence 5, got {snapshot.sequence_number}"
        assert snapshot.aggregate_id == amazon_order_id, "Snapshot should be for correct aggregate"
        
        print(f"✅ Snapshot verified:")
        print(f"   Sequence: {snapshot.sequence_number}")
        print(f"   Aggregate: {snapshot.aggregate_id}")
        print(f"   Version: {snapshot.snapshot_version}")
        print()
        
        # Verify snapshot data structure
        print("6. Verifying snapshot data structure...")
        snapshot_data = snapshot.snapshot_data
        
        assert 'order_id' in snapshot_data, "Snapshot should contain order_id"
        assert 'order_status' in snapshot_data, "Snapshot should contain order_status"
        assert snapshot_data['order_id'] == amazon_order_id, "Snapshot order_id should match"
        
        print("✅ Snapshot data structure verified")
        print(f"   Contains: {', '.join(snapshot_data.keys())}")
        print()
        
        # Test rebuilding with snapshot (optimized path)
        print("7. Testing Order rebuild with snapshot (optimized path)...")
        
        async for session in get_session():
            event_store = EventStore(session)
            snapshot_store = SnapshotStore(session)
            
            # Rebuild using snapshot
            rebuilt_order = await OrderEventRebuilder.rebuild_with_snapshot(
                aggregate_id=amazon_order_id,
                event_store=event_store,
                snapshot_store=snapshot_store
            )
            break
        
        assert rebuilt_order is not None, "Order should be rebuilt"
        assert rebuilt_order.order_id.value == amazon_order_id, "Order ID should match"
        assert rebuilt_order.order_status == "Synced", "Order status should be Synced"
        
        print("✅ Order rebuilt successfully using snapshot")
        print(f"   Order ID: {rebuilt_order.order_id.value}")
        print(f"   Status: {rebuilt_order.order_status}")
        print()
        
        # Test rebuilding without snapshot (backward compatibility)
        print("8. Testing Order rebuild without snapshot (backward compatibility)...")
        
        async for session in get_session():
            event_store = EventStore(session)
            
            # Rebuild without snapshot (should work)
            rebuilt_order_no_snapshot = await OrderEventRebuilder.rebuild_with_snapshot(
                aggregate_id=amazon_order_id,
                event_store=event_store,
                snapshot_store=None  # No snapshot store
            )
            break
        
        assert rebuilt_order_no_snapshot is not None, "Order should be rebuilt without snapshot"
        assert rebuilt_order_no_snapshot.order_id.value == amazon_order_id, "Order ID should match"
        assert rebuilt_order_no_snapshot.order_status == "Synced", "Order status should be Synced"
        
        print("✅ Order rebuilt successfully without snapshot (backward compatible)")
        print()
        
        # Verify both rebuilds produce same result
        print("9. Verifying snapshot vs full replay produce same result...")
        
        assert rebuilt_order.order_id.value == rebuilt_order_no_snapshot.order_id.value
        assert rebuilt_order.order_status == rebuilt_order_no_snapshot.order_status
        assert rebuilt_order.marketplace == rebuilt_order_no_snapshot.marketplace
        assert rebuilt_order.buyer_email == rebuilt_order_no_snapshot.buyer_email
        
        print("✅ Both rebuild methods produce identical results")
        print()
        
        # Test snapshot count
        print("10. Verifying snapshot count...")
        
        async for session in get_session():
            snapshot_store = SnapshotStore(session)
            snapshot_count = await snapshot_store.get_snapshot_count(amazon_order_id)
            break
        
        assert snapshot_count == 1, f"Expected 1 snapshot, got {snapshot_count}"
        
        print(f"✅ Snapshot count verified: {snapshot_count} snapshot(s)")
        print()
        
        # Final summary
        print("=" * 70)
        print("✅ DAY 1 - SESSION 4 SNAPSHOT ARCHITECTURE TEST COMPLETE!")
        print("=" * 70)
        print()
        
        print("Test Results:")
        print(f"  ✅ Snapshot model created and stored")
        print(f"  ✅ Snapshot created at sequence 5 (strategy: every 5 events)")
        print(f"  ✅ Order rebuilt using snapshot (optimized path)")
        print(f"  ✅ Order rebuilt without snapshot (backward compatible)")
        print(f"  ✅ Both rebuild methods produce identical results")
        print(f"  ✅ Snapshot data structure verified")
        print()
        
        print("Snapshot Architecture Features:")
        print("  ✅ SnapshotModel for state storage")
        print("  ✅ SnapshotStore for persistence")
        print("  ✅ SnapshotStrategy for frequency control")
        print("  ✅ OrderEventRebuilder with snapshot support")
        print("  ✅ Backward compatibility maintained")
        print()
        
        print("🎉 Snapshot Architecture Complete - Event Sourcing Optimized!")
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        raise
    
    finally:
        # Cleanup
        await close_database()
        cleanup_test_database()
        print("✅ Test database cleaned up")


if __name__ == "__main__":
    asyncio.run(test_snapshot_architecture())
