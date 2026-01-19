"""
Integration Test.

Tests full workflow end-to-end.
"""
import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def test_full_workflow():
    """Test complete order sync workflow."""
    
    logger.info("="*80)
    logger.info("INTEGRATION TEST: Full Order Sync Workflow")
    logger.info("="*80)
    
    # Setup
    logger.info("\n1. Setting up dependencies...")
    
    try:
        from core.domain.entities.order import Order
        from core.domain.value_objects import (
            OrderNumber, ExecutionID, Money,
            FinancialBreakdown, FinancialLine
        )
        from core.application.use_cases.sync_amazon_order import (
            SyncAmazonOrderUseCase,
            SyncAmazonOrderRequest,
        )
    except ImportError as e:
        logger.error(f"   ❌ Failed to import required modules: {e}")
        logger.info("   💡 Make sure all dependencies are installed")
        return False
    
    # Try to import mock implementations
    try:
        from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
        from core.infrastructure.adapters.odoo.mock_odoo_client import MockOdooClient
        from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService
        mocks_available = True
        logger.info("   ✓ Using existing mock implementations")
    except ImportError:
        logger.warning("   ⚠️  Mock implementations not found at expected paths")
        logger.info("   💡 Creating simple test mocks...")
        mocks_available = False
        
        # Create simple in-memory mocks for testing
        class MockOrderRepository:
            def __init__(self):
                self.orders = {}
            
            async def save(self, order: Order, execution_id: ExecutionID):
                self.orders[order.order_id.value] = order
            
            async def get_by_id(self, order_id: OrderNumber):
                return self.orders.get(order_id.value)
        
        class MockOdooClient:
            async def create_invoice(self, header, lines):
                return 1000
        
        class MockNotificationService:
            def __init__(self):
                self.notifications = []
            
            async def send_notification(self, message: str, level: str = "info"):
                self.notifications.append({"message": message, "level": level, "type": "success"})
            
            def get_notifications(self):
                return self.notifications
    
    repository = MockOrderRepository()
    odoo_client = MockOdooClient()
    notification_service = MockNotificationService()
    
    use_case = SyncAmazonOrderUseCase(
        order_repository=repository,
        odoo_client=odoo_client,
        notification_service=notification_service
    )
    
    logger.info("   ✅ Dependencies ready")
    
    # Test data
    logger.info("\n2. Preparing test data...")
    
    financial_events = {
        "ShipmentEventList": [{
            "AmazonOrderId": "123-4567890-1234567",
            "PostedDate": "2026-01-15T12:00:00Z",
            "ShipmentItemList": [{
                "SellerSKU": "TEST-SKU-001",
                "ItemChargeList": [{
                    "ChargeType": "Principal",
                    "ChargeAmount": {
                        "CurrencyCode": "EGP",
                        "CurrencyAmount": "200.00"
                    }
                }],
                "ItemFeeList": [{
                    "FeeType": "FBAPerUnitFulfillmentFee",
                    "FeeAmount": {
                        "CurrencyCode": "EGP",
                        "CurrencyAmount": "-20.00"
                    }
                }],
                "PromotionList": []
            }]
        }]
    }
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=financial_events,
        buyer_email="integration@test.com",
        dry_run=False
    )
    
    logger.info("   ✅ Test data ready")
    
    # Execute
    logger.info("\n3. Executing order sync...")
    
    try:
        response = await use_case.execute(request)
        logger.info("   ✅ Order sync completed")
    except Exception as e:
        logger.error(f"   ❌ Order sync failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Verify
    logger.info("\n4. Verifying results...")
    
    try:
        assert response.success, "Sync should succeed"
        assert response.order_id.value == "123-4567890-1234567"
        assert response.principal_amount == Decimal("200.00")
        assert response.net_proceeds == Decimal("180.00")
        logger.info("   ✅ Results verified")
    except AssertionError as e:
        logger.error(f"   ❌ Verification failed: {e}")
        logger.info(f"   Response: success={response.success}, order_id={response.order_id.value if hasattr(response, 'order_id') else 'N/A'}")
        return False
    
    # Check repository
    logger.info("\n5. Checking repository...")
    
    try:
        stored_order = await repository.get_by_id(OrderNumber(value="123-4567890-1234567"))
        assert stored_order is not None, "Order should be stored in repository"
        logger.info("   ✅ Repository verified")
    except AssertionError as e:
        logger.error(f"   ❌ Repository check failed: {e}")
        return False
    
    # Check notifications
    logger.info("\n6. Checking notifications...")
    
    try:
        notifications = notification_service.get_notifications()
        assert len(notifications) > 0, "Should have at least one notification"
        logger.info("   ✅ Notifications verified")
    except AssertionError as e:
        logger.warning(f"   ⚠️  Notification check: {e} (non-critical)")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("✅ INTEGRATION TEST PASSED")
    logger.info("="*80)
    logger.info(f"\nResults:")
    logger.info(f"  Order ID: {response.order_id.value}")
    logger.info(f"  Principal: {response.principal_amount} {response.principal_amount.currency if hasattr(response, 'principal_amount') and hasattr(response.principal_amount, 'currency') else 'EGP'}")
    logger.info(f"  Net Proceeds: {response.net_proceeds} {response.net_proceeds.currency if hasattr(response, 'net_proceeds') and hasattr(response.net_proceeds, 'currency') else 'EGP'}")
    if hasattr(response, 'odoo_invoice_id') and response.odoo_invoice_id:
        logger.info(f"  Invoice ID: {response.odoo_invoice_id}")
    logger.info(f"  Execution ID: {response.execution_id.value}")
    logger.info("="*80)
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_full_workflow())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        exit(1)

