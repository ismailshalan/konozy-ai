"""
Amazon Sync Service.

High-level service that coordinates Amazon order synchronization.
This is a facade over the use cases, providing a simple API.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import time

from core.application.use_cases.sync_amazon_order import (
    SyncAmazonOrderUseCase,
    SyncAmazonOrderRequest,
    SyncAmazonOrderResponse,
)
from core.domain.value_objects import ExecutionID
from core.domain.entities.order import Order
from core.data.uow import UnitOfWork, create_uow
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.database.config import get_session_factory
from core.domain.events.order_events import (
    OrderFetchedEvent,
    InvoiceCreatedEvent,
    InvoiceFailedEvent,
    SyncStartedEvent,
    SyncCompletedEvent,
)
from core.application.interfaces import INotificationService


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
    
    def __init__(
        self,
        sync_order_use_case: SyncAmazonOrderUseCase,
        amazon_order_client=None,
        odoo_client=None,
        session_factory=None,
        notification_service: Optional[INotificationService] = None,
    ):
        """
        Initialize service.
        
        Args:
            sync_order_use_case: Use case for syncing single order
            amazon_order_client: AmazonOrderClient for fetching orders
            odoo_client: OdooClient for creating invoices
            session_factory: Session factory for database operations
            notification_service: Notification service for sending alerts
        """
        self.sync_order_use_case = sync_order_use_case
        self._amazon_order_client = amazon_order_client
        self._odoo_client = odoo_client
        self._session_factory = session_factory or get_session_factory()
        self._notification_service = notification_service
    
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
    
    async def sync_orders(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        execution_id: Optional[ExecutionID] = None,
    ) -> Dict[str, Any]:
        """
        Sync orders from Amazon SP-API.
        
        This method orchestrates the complete sync workflow:
        1. Fetch orders from Amazon
        2. Map to domain entities
        3. Save to database
        4. Create invoices in Odoo
        5. Log events
        
        Args:
            start_date: Optional start date for filtering orders
            end_date: Optional end date for filtering orders
            execution_id: Optional execution ID (generated if not provided)
            
        Returns:
            Dictionary with sync summary:
            - execution_id: Execution ID for tracking
            - total_orders: Total orders fetched
            - created_invoices: Number of invoices created
            - failed_items: List of failed orders
            - successful: Number of successful syncs
        """
        # Generate execution_id if not provided
        if execution_id is None:
            execution_id = ExecutionID.generate()
        
        logger.info(
            f"[{execution_id}] Starting order sync - "
            f"start_date={start_date}, end_date={end_date}"
        )
        
        execution_id_str = str(execution_id.value)
        
        # Initialize results
        total_orders = 0
        created_invoices = 0
        invoices_failed = 0
        failed_items = []
        successful = 0
        
        # Create UoW for event emission
        uow = create_uow(self._session_factory)
        async with uow:
            event_store = EventStore(uow._session)
            
            # Emit SyncStartedEvent
            sync_started_event = SyncStartedEvent(
                aggregate_id=f"sync-{execution_id_str}",
                execution_id=execution_id_str,
                marketplace="amazon",
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
            )
            await event_store.append(sync_started_event)
            await uow.commit()
        
        try:
            # Step 1: Fetch orders from Amazon using SDK
            if not self._amazon_order_client:
                raise RuntimeError("AmazonAPI not configured")
            
            logger.info(f"[{execution_id}] Fetching orders from Amazon SP-API")
            # AmazonAPI.get_orders() is sync, so we run it in executor
            import asyncio
            loop = asyncio.get_event_loop()
            raw_orders = await loop.run_in_executor(
                None,
                lambda: self._amazon_order_client.get_orders(
                    created_after=start_date.isoformat() if start_date else "",
                    created_before=end_date.isoformat() if end_date else ""
                )
            )
            
            total_orders = len(raw_orders)
            logger.info(f"[{execution_id}] Fetched {total_orders} orders from Amazon")
            
            # Step 2: Process each order
            from core.domain.entities.order import Order, OrderItem
            from core.domain.value_objects import OrderNumber, Money
            from datetime import datetime
            from decimal import Decimal
            
            def map_amazon_order_to_domain(raw_order: dict, exec_id: ExecutionID) -> Order:
                """Convert raw Amazon order data to Order domain entity."""
                amazon_order_id = raw_order.get("AmazonOrderId")
                if not amazon_order_id:
                    raise ValueError("AmazonOrderId is required")
                
                purchase_date_str = raw_order.get("PurchaseDate")
                if not purchase_date_str:
                    raise ValueError("PurchaseDate is required")
                
                try:
                    purchase_date = datetime.fromisoformat(purchase_date_str.replace("Z", "+00:00"))
                except Exception:
                    purchase_date = datetime.utcnow()
                
                buyer_email = raw_order.get("BuyerInfo", {}).get("BuyerEmail")
                order_status = raw_order.get("OrderStatus", "Pending")
                
                order_total = None
                if "OrderTotal" in raw_order:
                    total_dict = raw_order["OrderTotal"]
                    order_total = Money(
                        amount=Decimal(str(total_dict.get("Amount", "0.00"))),
                        currency=total_dict.get("CurrencyCode", "EGP")
                    )
                
                items = []
                order_items = raw_order.get("OrderItems", [])
                for item_data in order_items:
                    item_total = None
                    if "ItemPrice" in item_data:
                        price_dict = item_data["ItemPrice"]
                        item_total = Money(
                            amount=Decimal(str(price_dict.get("Amount", "0.00"))),
                            currency=price_dict.get("CurrencyCode", "EGP")
                        )
                    
                    items.append(OrderItem(
                        sku=item_data.get("SellerSKU", ""),
                        title=item_data.get("Title"),
                        quantity=int(item_data.get("QuantityOrdered", 1)),
                        unit_price=Money(
                            amount=Decimal(str(item_data.get("ItemPrice", {}).get("Amount", "0.00"))),
                            currency=item_data.get("ItemPrice", {}).get("CurrencyCode", "EGP")
                        ) if "ItemPrice" in item_data else Money(amount=Decimal("0.00"), currency="EGP"),
                        total=item_total or Money(amount=Decimal("0.00"), currency="EGP"),
                    ))
                
                return Order(
                    order_id=OrderNumber(value=amazon_order_id),
                    purchase_date=purchase_date,
                    buyer_email=buyer_email or "",
                    items=items,
                    order_total=order_total,
                    order_status=order_status,
                    execution_id=exec_id,
                    marketplace="amazon",
                )
            
            uow = create_uow(self._session_factory)
            async with uow:
                event_store = EventStore(uow._session)
                
                for raw_order in raw_orders:
                    order_id_str = raw_order.get("AmazonOrderId") or raw_order.get("OrderId", "unknown")
                    
                    try:
                        # Map to domain entity
                        domain_order = map_amazon_order_to_domain(raw_order, execution_id)
                        domain_order.marketplace = "amazon"
                        
                        logger.info(
                            f"[{execution_id}] Processing order: {order_id_str}"
                        )
                        
                        # Save event: ORDER_FETCHED
                        order_fetched_event = OrderFetchedEvent(
                            aggregate_id=order_id_str,
                            execution_id=execution_id_str,
                            order_id=order_id_str,
                            marketplace="amazon",
                            buyer_email=domain_order.buyer_email,
                            purchase_date=domain_order.purchase_date.isoformat(),
                        )
                        await event_store.append(order_fetched_event)
                        
                        # Save order to repository
                        await uow.orders.save(domain_order, execution_id)
                        logger.info(
                            f"[{execution_id}] Order saved: {order_id_str}"
                        )
                        
                        # Step 3: Create invoice in Odoo
                        if self._odoo_client:
                            try:
                                invoice_id = await self._create_invoice_in_odoo(domain_order)
                                
                                if invoice_id:
                                    created_invoices += 1
                                    
                                    # Save event: INVOICE_CREATED
                                    invoice_created_event = InvoiceCreatedEvent(
                                        aggregate_id=order_id_str,
                                        execution_id=execution_id_str,
                                        order_id=order_id_str,
                                        invoice_id=invoice_id,
                                        partner_id=0,  # Will be set by Odoo
                                        invoice_lines_count=len(domain_order.items),
                                    )
                                    await event_store.append(invoice_created_event)
                                    
                                    logger.info(
                                        f"[{execution_id}] Invoice created in Odoo: "
                                        f"order={order_id_str}, invoice_id={invoice_id}"
                                    )
                            except Exception as invoice_error:
                                invoices_failed += 1
                                error_message = str(invoice_error)
                                
                                logger.error(
                                    f"[{execution_id}] Failed to create invoice for order "
                                    f"{order_id_str}: {invoice_error}",
                                    exc_info=True
                                )
                                
                                # Emit InvoiceFailedEvent
                                invoice_failed_event = InvoiceFailedEvent(
                                    aggregate_id=order_id_str,
                                    execution_id=execution_id_str,
                                    order_id=order_id_str,
                                    error_message=error_message,
                                    error_type="invoice_creation",
                                )
                                await event_store.append(invoice_failed_event)
                                
                                failed_items.append({
                                    "order_id": order_id_str,
                                    "error": error_message,
                                    "step": "invoice_creation"
                                })
                        else:
                            logger.warning(
                                f"[{execution_id}] Odoo client not configured, "
                                f"skipping invoice creation for order {order_id_str}"
                            )
                        
                        successful += 1
                        
                    except Exception as order_error:
                        logger.error(
                            f"[{execution_id}] Failed to process order {order_id_str}: {order_error}",
                            exc_info=True
                        )
                        failed_items.append({
                            "order_id": order_id_str,
                            "error": str(order_error),
                            "step": "order_processing"
                        })
                
                # Commit all changes
                await uow.commit()
                logger.info(
                    f"[{execution_id}] Transaction committed - "
                    f"successful={successful}, failed={len(failed_items)}"
                )
            
            logger.info(
                f"[{execution_id}] Order sync completed - "
                f"total={total_orders}, successful={successful}, "
                f"invoices={created_invoices}, failed={len(failed_items)}"
            )
            
            # Emit SyncCompletedEvent
            uow = create_uow(self._session_factory)
            async with uow:
                event_store = EventStore(uow._session)
                
                sync_completed_event = SyncCompletedEvent(
                    aggregate_id=f"sync-{execution_id_str}",
                    execution_id=execution_id_str,
                    marketplace="amazon",
                    total_orders=total_orders,
                    successful=successful,
                    failed=len(failed_items),
                    invoices_created=created_invoices,
                    invoices_failed=invoices_failed,
                )
                await event_store.append(sync_completed_event)
                await uow.commit()
            
            # Send notification
            if self._notification_service:
                try:
                    message = (
                        f"[KONOZY] Amazon sync completed | exec={execution_id_str} | "
                        f"orders={total_orders} | invoices_ok={created_invoices} | "
                        f"invoices_failed={invoices_failed}"
                    )
                    # Use a generic notify method if available, or send_success for now
                    # We'll add a notify method to the interface
                    if hasattr(self._notification_service, 'notify'):
                        await self._notification_service.notify(message, severity=80)
                    else:
                        # Fallback: log notification
                        logger.info(f"📢 Notification: {message}")
                except Exception as notify_error:
                    logger.warning(
                        f"[{execution_id}] Failed to send notification: {notify_error}",
                        exc_info=True
                    )
            
            return {
                "execution_id": execution_id_str,
                "total_orders": total_orders,
                "created_invoices": created_invoices,
                "invoices_failed": invoices_failed,
                "failed_items": failed_items,
                "successful": successful,
            }
            
        except Exception as e:
            logger.error(
                f"[{execution_id}] Order sync failed: {e}",
                exc_info=True
            )
            
            # Emit SyncCompletedEvent with failure status
            try:
                uow = create_uow(self._session_factory)
                async with uow:
                    event_store = EventStore(uow._session)
                    
                    sync_completed_event = SyncCompletedEvent(
                        aggregate_id=f"sync-{execution_id_str}",
                        execution_id=execution_id_str,
                        marketplace="amazon",
                        total_orders=total_orders,
                        successful=successful,
                        failed=len(failed_items) + 1,  # Include the sync failure
                        invoices_created=created_invoices,
                        invoices_failed=invoices_failed,
                    )
                    await event_store.append(sync_completed_event)
                    await uow.commit()
            except Exception as event_error:
                logger.error(f"Failed to emit SyncCompletedEvent: {event_error}")
            
            raise
    
    async def _create_invoice_in_odoo(self, order: Order) -> Optional[int]:
        """
        Create invoice in Odoo for the given order.
        
        Args:
            order: Domain Order entity
            
        Returns:
            Invoice ID if created successfully, None otherwise
        """
        if not self._odoo_client:
            return None
        
        try:
            # This is a placeholder - actual implementation would call Odoo API
            # For now, return None to indicate invoice creation is not implemented
            # In production, this would:
            # 1. Create partner if needed
            # 2. Create invoice with order items
            # 3. Return invoice ID
            
            logger.warning(
                f"Invoice creation for order {order.order_id.value} "
                f"not fully implemented yet"
            )
            return None
            
        except Exception as e:
            logger.error(f"Failed to create invoice in Odoo: {e}", exc_info=True)
            return None