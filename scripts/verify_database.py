"""
Verify database setup.

Tests database connection, models, and basic operations.
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal

from core.infrastructure.database.config import init_database, get_session, close_database
from core.infrastructure.database.unit_of_work import UnitOfWork
from core.domain.entities import Order
from core.domain.value_objects import (
    OrderNumber, ExecutionID, Money,
    FinancialBreakdown, FinancialLine
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_database():
    """Test database operations."""
    
    logger.info("="*80)
    logger.info("DATABASE VERIFICATION TEST")
    logger.info("="*80)
    
    try:
        # Initialize database
        logger.info("\n1. Initializing database...")
        await init_database()
        
        # Create test order
        logger.info("\n2. Creating test order...")
        
        breakdown = FinancialBreakdown(
            principal=Money(amount=Decimal("100.00"), currency="EGP"),
            financial_lines=[
                FinancialLine(
                    line_type="fee",
                    fee_type=None,
                    description="FBA Fee",
                    amount=Money(amount=Decimal("-10.00"), currency="EGP"),
                    sku="TEST-SKU"
                )
            ],
            net_proceeds=Money(amount=Decimal("90.00"), currency="EGP")
        )
        
        order = Order(
            order_id=OrderNumber(value="TEST-001-001-001"),
            purchase_date=datetime.utcnow(),
            buyer_email="test@example.com",
            financial_breakdown=breakdown,
            execution_id=ExecutionID.generate(),
            marketplace="amazon",
            order_status="Pending"
        )
        
        logger.info(f"✅ Test order created: {order.order_id.value}")
        
        # Save order
        logger.info("\n3. Saving order to database...")
        
        async for session in get_session():
            async with UnitOfWork(session) as uow:
                await uow.orders.save(order, order.execution_id)
                await uow.commit()
        
        logger.info("✅ Order saved successfully")
        
        # Retrieve order
        logger.info("\n4. Retrieving order from database...")
        
        retrieved_order = None
        async for session in get_session():
            async with UnitOfWork(session) as uow:
                retrieved_order = await uow.orders.get_by_id(
                    OrderNumber(value="TEST-001-001-001")
                )
        
        if retrieved_order:
            logger.info("✅ Order retrieved successfully")
            logger.info(f"   Order ID: {retrieved_order.order_id.value}")
            logger.info(f"   Status: {retrieved_order.order_status}")
            if retrieved_order.financial_breakdown:
                logger.info(f"   Principal: {retrieved_order.financial_breakdown.principal.amount} EGP")
                logger.info(f"   Net: {retrieved_order.financial_breakdown.net_proceeds.amount} EGP")
        else:
            logger.error("❌ Order not found!")
            return
        
        # Update order
        logger.info("\n5. Updating order...")
        
        async for session in get_session():
            async with UnitOfWork(session) as uow:
                order_to_update = await uow.orders.get_by_id(
                    OrderNumber(value="TEST-001-001-001")
                )
                
                if order_to_update:
                    order_to_update.mark_synced()
                    await uow.orders.save(order_to_update, order_to_update.execution_id or ExecutionID.generate())
                    await uow.commit()
        
        logger.info("✅ Order updated successfully")
        
        # Verify update
        logger.info("\n6. Verifying update...")
        
        updated_order = None
        async for session in get_session():
            async with UnitOfWork(session) as uow:
                updated_order = await uow.orders.get_by_id(
                    OrderNumber(value="TEST-001-001-001")
                )
        
        if updated_order and updated_order.order_status == "Synced":
            logger.info("✅ Update verified - status is 'Synced'")
        else:
            logger.error("❌ Update verification failed!")
            return
        
        # List all orders
        logger.info("\n7. Listing all orders...")
        
        all_orders = []
        async for session in get_session():
            async with UnitOfWork(session) as uow:
                all_orders = await uow.orders.find_all_async(limit=10)
        
        logger.info(f"✅ Found {len(all_orders)} order(s)")
        
        logger.info("\n" + "="*80)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        raise
    
    finally:
        # Cleanup
        await close_database()


if __name__ == "__main__":
    asyncio.run(test_database())
