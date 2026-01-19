"""
End-to-End Demo: Amazon Order Sync

This demonstrates the complete workflow:
1. Extract fees from Amazon Financial Events
2. Validate financials
3. Create order
4. Save to repository
5. Create Odoo invoice
6. Send notifications

Uses mock implementations (no real Odoo/database needed).
"""
import asyncio
import logging
import json
from decimal import Decimal
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import mock implementations
from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
from core.infrastructure.adapters.odoo.mock_odoo_client import MockOdooClient
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService

# Import use case
from core.application.use_cases.sync_amazon_order import (
    SyncAmazonOrderUseCase,
    SyncAmazonOrderRequest,
)

# Import service
from core.application.services.amazon_sync_service import AmazonSyncService


async def demo_single_order():
    """Demo: Sync single Amazon order."""
    
    print("\n" + "="*80)
    print("DEMO: Single Amazon Order Sync")
    print("="*80 + "\n")
    
    # =========================================================================
    # SETUP: Create mock dependencies
    # =========================================================================
    print("📦 Setting up mock dependencies...")
    
    repository = MockOrderRepository()
    odoo_client = MockOdooClient()
    notification_service = MockNotificationService()
    
    # Add test data to mocks
    odoo_client.add_partner("buyer@example.com", 999)
    odoo_client.add_product("JR-ZS283", 888)
    
    print("✅ Mock dependencies ready\n")
    
    # =========================================================================
    # CREATE USE CASE
    # =========================================================================
    print("🏗️ Creating use case...")
    
    use_case = SyncAmazonOrderUseCase(
        order_repository=repository,
        odoo_client=odoo_client,
        notification_service=notification_service
    )
    
    print("✅ Use case created\n")
    
    # =========================================================================
    # LOAD TEST DATA
    # =========================================================================
    print("📄 Loading test data...")
    
    # Try to load real Amazon Financial Events
    test_data_path = Path("tests/parity/data/raw_financial_events.json")
    
    financial_events = None
    order_id = "171-3372061-4556310"
    
    if test_data_path.exists():
        try:
            with open(test_data_path, encoding="utf-8") as f:
                data = json.load(f)
            
            # Extract first order's financial events
            events_list = data.get("الأحداث_المالية", {}).get("ShipmentEventList", [])
            if events_list:
                first_event = events_list[0]
                order_id = first_event.get("AmazonOrderId", order_id)
                financial_events = {"ShipmentEventList": [first_event]}
                print(f"✅ Loaded real test data from {test_data_path}")
                print(f"   Order ID: {order_id}\n")
        except Exception as e:
            logger.warning(f"Failed to load test data: {e}")
            financial_events = None
    
    if not financial_events:
        # Fallback: Create minimal test data
        financial_events = {
            "ShipmentEventList": [{
                "AmazonOrderId": order_id,
                "PostedDate": "2026-01-13T12:00:00Z",
                "BuyerInfo": {
                    "BuyerEmail": "buyer@example.com"
                },
                "ShipmentItemList": [{
                    "SellerSKU": "JR-ZS283",
                    "QuantityShipped": 1,
                    "ItemChargeList": [{
                        "ChargeType": "Principal",
                        "ChargeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": "198.83"
                        }
                    }],
                    "ItemFeeList": [{
                        "FeeType": "FBAPerUnitFulfillmentFee",
                        "FeeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": "-21.66"
                        }
                    }, {
                        "FeeType": "Commission",
                        "FeeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": "-27.21"
                        }
                    }],
                    "PromotionList": []
                }]
            }]
        }
        print("⚠️ Using fallback test data\n")
    
    # =========================================================================
    # EXECUTE USE CASE
    # =========================================================================
    print("🚀 Executing order sync...\n")
    print("-" * 80)
    
    request = SyncAmazonOrderRequest(
        amazon_order_id=order_id,
        financial_events=financial_events,
        buyer_email="buyer@example.com",
        dry_run=False
    )
    
    response = await use_case.execute(request)
    
    print("-" * 80)
    print("\n📊 RESULTS:")
    print(f"   Success: {response.success}")
    print(f"   Order ID: {response.order_id.value}")
    print(f"   Execution ID: {response.execution_id.value}")
    if response.principal_amount:
        print(f"   Principal: {response.principal_amount} EGP")
    if response.net_proceeds:
        print(f"   Net Proceeds: {response.net_proceeds} EGP")
    print(f"   Odoo Invoice ID: {response.odoo_invoice_id}")
    
    if response.error:
        print(f"   Error: {response.error}")
        if response.error_details:
            print(f"   Details: {response.error_details}")
    
    print("\n" + "="*80)
    print("✅ Single order demo completed!")
    print("="*80 + "\n")
    
    return response


async def demo_batch_orders():
    """Demo: Sync multiple orders in batch."""
    
    print("\n" + "="*80)
    print("DEMO: Batch Order Sync (3 orders)")
    print("="*80 + "\n")
    
    # Setup
    repository = MockOrderRepository()
    odoo_client = MockOdooClient()
    notification_service = MockNotificationService()
    
    use_case = SyncAmazonOrderUseCase(
        order_repository=repository,
        odoo_client=odoo_client,
        notification_service=notification_service
    )
    
    service = AmazonSyncService(sync_order_use_case=use_case)
    
    # Prepare batch data
    orders_data = [
        {
            "order_id": "407-1263947-9146736",
            "financial_events": {
                "ShipmentEventList": [{
                    "AmazonOrderId": "407-1263947-9146736",
                    "PostedDate": "2026-01-13T12:00:00Z",
                    "ShipmentItemList": [{
                        "SellerSKU": "SKU-A",
                        "QuantityShipped": 1,
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {"CurrencyCode": "EGP", "CurrencyAmount": "100.00"}
                        }],
                        "ItemFeeList": [],
                        "PromotionList": []
                    }]
                }]
            }
        },
        {
            "order_id": "408-8327146-7101142",
            "financial_events": {
                "ShipmentEventList": [{
                    "AmazonOrderId": "408-8327146-7101142",
                    "PostedDate": "2026-01-13T12:00:00Z",
                    "ShipmentItemList": [{
                        "SellerSKU": "SKU-B",
                        "QuantityShipped": 1,
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {"CurrencyCode": "EGP", "CurrencyAmount": "200.00"}
                        }],
                        "ItemFeeList": [],
                        "PromotionList": []
                    }]
                }]
            }
        },
        {
            "order_id": "409-9876543-2109876",
            "financial_events": {
                "ShipmentEventList": [{
                    "AmazonOrderId": "409-9876543-2109876",
                    "PostedDate": "2026-01-13T12:00:00Z",
                    "ShipmentItemList": [{
                        "SellerSKU": "SKU-C",
                        "QuantityShipped": 1,
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {"CurrencyCode": "EGP", "CurrencyAmount": "300.00"}
                        }],
                        "ItemFeeList": [],
                        "PromotionList": []
                    }]
                }]
            }
        }
    ]
    
    # Execute batch
    print("🚀 Syncing batch of 3 orders...\n")
    print("-" * 80)
    
    responses = await service.sync_multiple_orders(
        orders_data=orders_data,
        continue_on_error=True,
        dry_run=False
    )
    
    print("-" * 80)
    
    # Get statistics
    stats = await service.get_sync_statistics(responses)
    
    print("\n📊 BATCH RESULTS:")
    print(f"   Total Orders: {stats['total_orders']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
    print(f"   Success Rate: {stats['success_rate']:.1f}%")
    print(f"   Total Principal: {stats['total_principal']} EGP")
    print(f"   Total Net Proceeds: {stats['total_net_proceeds']} EGP")
    
    print("\n" + "="*80)
    print("✅ Batch demo completed!")
    print("="*80 + "\n")


async def main():
    """Run all demos."""
    
    print("\n" + "🎬 " * 20)
    print("KONOZY AI - END-TO-END DEMO")
    print("Amazon Order Sync with Clean Architecture")
    print("🎬 " * 20 + "\n")
    
    try:
        # Demo 1: Single order
        await demo_single_order()
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Demo 2: Batch orders
        await demo_batch_orders()
        
        print("\n✅ All demos completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
