"""
Amazon Sync Service.

High-level service that coordinates Amazon order synchronization.
This is a facade over the use cases, providing a simple API.
"""
from typing import List, Optional
import logging
import time

from core.application.use_cases.sync_amazon_order import (
    SyncAmazonOrderUseCase,
    SyncAmazonOrderRequest,
    SyncAmazonOrderResponse,
)


logger = logging.getLogger(__name__)


class AmazonSyncService:
    """
    Service for syncing Amazon orders.
    
    This is a high-level orchestration service that provides
    a simple interface for order synchronization.
    
    Usage:
        service = AmazonSyncService(sync_order_use_case)
        
        # Single order
        response = await service.sync_single_order(
            order_id="407-1263947-9146736",
            financial_events={...}
        )
        
        # Batch orders
        responses = await service.sync_multiple_orders([...])
    """
    
    def __init__(self, sync_order_use_case: SyncAmazonOrderUseCase):
        """
        Initialize service.
        
        Args:
            sync_order_use_case: Use case for syncing single order
        """
        self.sync_order_use_case = sync_order_use_case
    
    async def sync_single_order(
        self,
        order_id: str,
        financial_events: dict,
        buyer_email: Optional[str] = None,
        dry_run: bool = False
    ) -> SyncAmazonOrderResponse:
        """
        Sync single Amazon order.
        
        Args:
            order_id: Amazon order ID
            financial_events: Financial events from Amazon API
            buyer_email: Optional buyer email for Odoo partner lookup
            dry_run: If True, validates without creating invoice
        
        Returns:
            Sync response with results
        """
        logger.info(f"Syncing single order: {order_id} (dry_run={dry_run})")
        
        request = SyncAmazonOrderRequest(
            amazon_order_id=order_id,
            financial_events=financial_events,
            buyer_email=buyer_email,
            dry_run=dry_run
        )
        
        response = await self.sync_order_use_case.execute(request)
        
        if response.success:
            logger.info(
                f"✅ Order {order_id} synced successfully. "
                f"Invoice ID: {response.odoo_invoice_id}"
            )
        else:
            logger.error(
                f"❌ Order {order_id} sync failed: {response.error}"
            )
        
        return response
    
    async def sync_multiple_orders(
        self,
        orders_data: List[dict],
        continue_on_error: bool = True,
        dry_run: bool = False
    ) -> List[SyncAmazonOrderResponse]:
        """
        Sync multiple Amazon orders in batch.
        
        Args:
            orders_data: List of order data dicts, each containing:
                        - order_id: Amazon order ID
                        - financial_events: Financial events
                        - buyer_email: Optional buyer email
            continue_on_error: If True, continues even if some orders fail
            dry_run: If True, validates without creating invoices
        
        Returns:
            List of sync responses
        """
        logger.info(
            f"Syncing batch of {len(orders_data)} orders "
            f"(continue_on_error={continue_on_error}, dry_run={dry_run})"
        )
        
        start_time = time.time()
        responses = []
        successful = 0
        failed = 0
        
        for i, order_data in enumerate(orders_data, 1):
            order_id = order_data.get("order_id")
            
            logger.info(f"Processing order {i}/{len(orders_data)}: {order_id}")
            
            try:
                response = await self.sync_single_order(
                    order_id=order_id,
                    financial_events=order_data.get("financial_events"),
                    buyer_email=order_data.get("buyer_email"),
                    dry_run=dry_run
                )
                
                responses.append(response)
                
                if response.success:
                    successful += 1
                else:
                    failed += 1
                    
                    if not continue_on_error:
                        logger.error(
                            f"Order {order_id} failed and continue_on_error=False. "
                            f"Stopping batch."
                        )
                        break
            
            except Exception as e:
                logger.error(
                    f"Unexpected error processing order {order_id}: {e}",
                    exc_info=True
                )
                
                failed += 1
                
                # Create error response
                from core.domain.value_objects import OrderNumber, ExecutionID
                responses.append(
                    SyncAmazonOrderResponse(
                        execution_id=ExecutionID.generate(),
                        order_id=OrderNumber(value=order_id),
                        success=False,
                        error="Unexpected error",
                        error_details=str(e)
                    )
                )
                
                if not continue_on_error:
                    logger.error(
                        f"Unexpected error and continue_on_error=False. "
                        f"Stopping batch."
                    )
                    break
        
        elapsed_time = time.time() - start_time
        
        logger.info(
            f"Batch sync completed in {elapsed_time:.2f}s: "
            f"{successful} successful, {failed} failed out of {len(orders_data)} total"
        )
        
        return responses
    
    async def get_sync_statistics(
        self,
        responses: List[SyncAmazonOrderResponse]
    ) -> dict:
        """
        Calculate statistics from sync responses.
        
        Args:
            responses: List of sync responses
        
        Returns:
            Dictionary with statistics
        """
        total = len(responses)
        successful = sum(1 for r in responses if r.success)
        failed = total - successful
        
        total_principal = sum(
            r.principal_amount for r in responses 
            if r.principal_amount is not None
        )
        
        total_net_proceeds = sum(
            r.net_proceeds for r in responses 
            if r.net_proceeds is not None
        )
        
        return {
            "total_orders": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "total_principal": float(total_principal),
            "total_net_proceeds": float(total_net_proceeds),
        }
