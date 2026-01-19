"""
Sync Amazon Order Use Case.

This is the CORE business logic for syncing Amazon orders to Odoo.

CRITICAL: This handles financial data - every line is important!

Flow:
1. Extract financial breakdown from Amazon API
2. Create Order entity with validation
3. Save to database (with transaction)
4. Create Odoo invoice
5. Send notifications
6. Handle errors gracefully
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging

from core.domain.entities.order import Order
from core.domain.value_objects import (
    OrderNumber,
    ExecutionID,
    Money,
    FinancialBreakdown,
)
from core.domain.repositories.order_repository import OrderRepository
from core.domain.event_bus import EventBus
from core.infrastructure.adapters.amazon.fee_mapper import AmazonFeeMapper
from core.infrastructure.adapters.odoo.odoo_financial_mapper import OdooFinancialMapper
from core.application.interfaces import IOdooClient, INotificationService
from core.infrastructure.database.snapshot_store import SnapshotStore
from core.infrastructure.database.snapshot_strategy import (
    SnapshotStrategy,
    DEFAULT_SNAPSHOT_STRATEGY
)
from core.infrastructure.database.config import get_session


logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST / RESPONSE DTOs (Application Layer)
# =============================================================================

@dataclass
class SyncAmazonOrderRequest:
    """
    Input for sync Amazon order use case.
    
    This is application-level request (not API-level).
    """
    amazon_order_id: str
    financial_events: Dict[str, Any]
    buyer_email: Optional[str] = None
    dry_run: bool = False


@dataclass
class SyncAmazonOrderResponse:
    """
    Output from sync Amazon order use case.
    
    Contains all information about the sync operation.
    """
    execution_id: ExecutionID
    order_id: OrderNumber
    success: bool
    
    # Financial data
    principal_amount: Optional[Decimal] = None
    net_proceeds: Optional[Decimal] = None
    
    # Odoo data
    odoo_invoice_id: Optional[int] = None
    
    # Error data
    error: Optional[str] = None
    error_details: Optional[str] = None
    
    # Metadata
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())


# =============================================================================
# USE CASE
# =============================================================================

class SyncAmazonOrderUseCase:
    """
    Use case for syncing Amazon order to Odoo.
    
    This orchestrates the complete business workflow:
    1. Extract financial data from Amazon
    2. Create and validate Order entity
    3. Save to database
    4. Create Odoo invoice
    5. Send notifications
    
    CRITICAL: This handles money - every step must be auditable.
    """
    
    def __init__(
        self,
        order_repository: OrderRepository,
        odoo_client: IOdooClient,
        notification_service: INotificationService,
        event_bus: EventBus,
        snapshot_strategy: Optional[SnapshotStrategy] = None,
    ):
        """
        Initialize use case with dependencies.
        
        Args:
            order_repository: Repository for order persistence
            odoo_client: Client for Odoo ERP integration
            notification_service: Service for sending notifications
            event_bus: Event Bus for publishing domain events
            snapshot_strategy: Optional snapshot strategy (default: every 10 events)
        """
        self.order_repository = order_repository
        self.odoo_client = odoo_client
        self.notification_service = notification_service
        self.event_bus = event_bus
        self.snapshot_strategy = snapshot_strategy or DEFAULT_SNAPSHOT_STRATEGY
    
    async def execute(
        self,
        request: SyncAmazonOrderRequest
    ) -> SyncAmazonOrderResponse:
        """
        Execute the sync workflow.
        
        This is the main entry point for syncing an Amazon order.
        
        Args:
            request: Sync request with order data
        
        Returns:
            Response with sync results
        
        Raises:
            No exceptions - all errors are caught and returned in response
        """
        execution_id = ExecutionID.generate()
        order_id = OrderNumber(value=request.amazon_order_id)
        
        logger.info(
            f"[{execution_id}] Starting Amazon order sync: {request.amazon_order_id}"
        )
        
        try:
            # ================================================================
            # STEP 1: Extract Financial Breakdown
            # ================================================================
            logger.info(f"[{execution_id}] Step 1: Extracting financial data")
            
            breakdown = AmazonFeeMapper.parse_financial_events(
                financial_events=request.financial_events,
                order_id=request.amazon_order_id
            )
            
            logger.info(
                f"[{execution_id}] Financial breakdown extracted: "
                f"Principal={breakdown.principal.amount}, "
                f"Net={breakdown.net_proceeds.amount}"
            )
            
            # Extract SKU-level principal (for multi-item orders)
            sku_to_principal = AmazonFeeMapper.extract_sku_to_principal(
                request.financial_events
            )
            
            logger.info(
                f"[{execution_id}] SKU-level principal: "
                f"{len(sku_to_principal)} SKU(s)"
            )
            
            # ================================================================
            # STEP 2: Create Order Entity
            # ================================================================
            logger.info(f"[{execution_id}] Step 2: Creating Order entity")
            
            order = Order(
                order_id=order_id,
                purchase_date=breakdown.posted_date or datetime.utcnow(),
                buyer_email=request.buyer_email or "",
                financial_breakdown=breakdown,
                execution_id=execution_id,
                marketplace="amazon",
                order_status="Pending",
            )
            
            logger.info(f"[{execution_id}] Order entity created")
            
            # Collect and publish initial events (OrderCreatedEvent, FinancialsExtractedEvent)
            initial_events = order.get_events()
            if initial_events:
                logger.info(f"[{execution_id}] Publishing {len(initial_events)} initial events")
                await self.event_bus.publish_all(initial_events)
                order.clear_events()
                logger.info(f"[{execution_id}] ✅ Initial events published and stored")
                
                # Create snapshot if needed (after events are committed)
                await self._maybe_create_snapshot(order, execution_id)
            
            # ================================================================
            # STEP 3: Validate Financials (CRITICAL!)
            # ================================================================
            logger.info(f"[{execution_id}] Step 3: Validating financials")
            
            try:
                order.validate_financials()
                logger.info(
                    f"[{execution_id}] ✅ Financial validation passed: "
                    f"Balance equation valid"
                )
                
                # Collect and publish validation event
                validation_events = order.get_events()
                if validation_events:
                    logger.info(f"[{execution_id}] Publishing validation event")
                    await self.event_bus.publish_all(validation_events)
                    order.clear_events()
                    logger.info(f"[{execution_id}] ✅ Validation event published")
                    
            except ValueError as e:
                logger.error(
                    f"[{execution_id}] ❌ Financial validation FAILED: {e}"
                )
                
                # Publish validation failure event before raising
                validation_events = order.get_events()
                if validation_events:
                    try:
                        await self.event_bus.publish_all(validation_events)
                        order.clear_events()
                    except Exception as pub_error:
                        logger.warning(f"[{execution_id}] Failed to publish validation failure event: {pub_error}")
                
                raise
            
            # ================================================================
            # STEP 4: Save to Database (if not dry-run)
            # ================================================================
            if not request.dry_run:
                logger.info(f"[{execution_id}] Step 4: Saving order to database")
                
                try:
                    await self.order_repository.save(order, execution_id)
                    logger.info(f"[{execution_id}] ✅ Order saved successfully")
                    
                    # Record order saved event
                    order.record_order_saved(database_id=str(execution_id.value))
                    
                    # Collect and publish order saved event
                    saved_events = order.get_events()
                    if saved_events:
                        logger.info(f"[{execution_id}] Publishing order saved event")
                        await self.event_bus.publish_all(saved_events)
                        order.clear_events()
                        logger.info(f"[{execution_id}] ✅ Order saved event published")
                        
                        # Create snapshot if needed
                        await self._maybe_create_snapshot(order, execution_id)
                        
                except Exception as e:
                    logger.error(
                        f"[{execution_id}] ❌ Database save failed: {e}"
                    )
                    raise
            else:
                logger.info(
                    f"[{execution_id}] Skipping database save (dry-run mode)"
                )
            
            # ================================================================
            # STEP 5: Lookup Partner in Odoo
            # ================================================================
            logger.info(f"[{execution_id}] Step 5: Looking up Odoo partner")
            
            partner_id = None
            if request.buyer_email:
                try:
                    partner_id = await self.odoo_client.get_partner_by_email(
                        request.buyer_email
                    )
                    
                    if partner_id:
                        logger.info(
                            f"[{execution_id}] Found partner: {partner_id}"
                        )
                    else:
                        logger.warning(
                            f"[{execution_id}] Partner not found for: "
                            f"{request.buyer_email}, using default"
                        )
                        partner_id = 1  # Default partner
                except Exception as e:
                    logger.warning(
                        f"[{execution_id}] Partner lookup failed: {e}, "
                        f"using default"
                    )
                    partner_id = 1
            else:
                logger.info(f"[{execution_id}] No email provided, using default partner")
                partner_id = 1
            
            # ================================================================
            # STEP 6: Create Odoo Invoice (if not dry-run)
            # ================================================================
            odoo_invoice_id = None
            
            if not request.dry_run:
                logger.info(f"[{execution_id}] Step 6: Creating Odoo invoice")
                
                try:
                    # Generate invoice header (using Order entity)
                    invoice_header = OdooFinancialMapper.to_invoice_header(order=order)
                    # Add partner_id to header
                    invoice_header["partner_id"] = partner_id
                    
                    # Generate invoice lines
                    invoice_lines = OdooFinancialMapper.to_invoice_lines(
                        breakdown=breakdown,
                        sku_to_principal=sku_to_principal
                    )
                    
                    # Create invoice in Odoo
                    odoo_invoice_id = await self.odoo_client.create_invoice(
                        header=invoice_header,
                        lines=invoice_lines
                    )
                    
                    logger.info(
                        f"[{execution_id}] ✅ Odoo invoice created: {odoo_invoice_id}"
                    )
                    
                    # Record invoice created event
                    order.record_invoice_created(
                        invoice_id=odoo_invoice_id,
                        partner_id=partner_id,
                        lines_count=len(invoice_lines)
                    )
                    
                    # Update order status (records OrderSyncedEvent)
                    order.mark_synced()
                    
                    # Collect all events (invoice created + synced)
                    sync_events = order.get_events()
                    
                    # Update in database
                    await self.order_repository.save(order, execution_id)
                    
                    # Publish all events atomically
                    if sync_events:
                        logger.info(f"[{execution_id}] Publishing {len(sync_events)} sync events")
                        await self.event_bus.publish_all(sync_events)
                        order.clear_events()
                        logger.info(f"[{execution_id}] ✅ Sync events published and stored")
                        
                        # Create snapshot if needed (after sync completion)
                        await self._maybe_create_snapshot(order, execution_id)
                    
                except Exception as e:
                    logger.error(
                        f"[{execution_id}] ❌ Odoo invoice creation failed: {e}"
                    )
                    
                    # Mark order as failed (records OrderFailedEvent)
                    order.mark_failed(str(e), error_details=str(e))
                    
                    # Collect failure event
                    failure_events = order.get_events()
                    
                    # Update in database
                    await self.order_repository.save(order, execution_id)
                    
                    # Publish failure event
                    if failure_events:
                        try:
                            await self.event_bus.publish_all(failure_events)
                            order.clear_events()
                        except Exception as pub_error:
                            logger.warning(f"[{execution_id}] Failed to publish failure event: {pub_error}")
                    
                    raise
            else:
                logger.info(
                    f"[{execution_id}] Skipping Odoo invoice creation (dry-run mode)"
                )
            
            # ================================================================
            # STEP 7: Send Success Notification
            # ================================================================
            logger.info(f"[{execution_id}] Step 7: Sending success notification")
            
            try:
                await self.notification_service.send_success(
                    execution_id=execution_id,
                    order_id=request.amazon_order_id,
                    odoo_invoice_id=odoo_invoice_id,
                    message=f"Order synced successfully. Net proceeds: {breakdown.net_proceeds}"
                )
            except Exception as e:
                # Don't fail the whole operation if notification fails
                logger.warning(
                    f"[{execution_id}] Notification failed (non-critical): {e}"
                )
            
            # ================================================================
            # SUCCESS RESPONSE
            # ================================================================
            logger.info(
                f"[{execution_id}] ✅ Amazon order sync completed successfully"
            )
            
            return SyncAmazonOrderResponse(
                execution_id=execution_id,
                order_id=order_id,
                success=True,
                principal_amount=breakdown.principal.amount,
                net_proceeds=breakdown.net_proceeds.amount,
                odoo_invoice_id=odoo_invoice_id,
                error=None,
                error_details=None
            )
        
        except ValueError as e:
            # Validation errors
            logger.error(
                f"[{execution_id}] ❌ Validation error: {e}"
            )
            
            try:
                await self.notification_service.send_error(
                    execution_id=execution_id,
                    order_id=request.amazon_order_id,
                    error=f"Validation failed: {str(e)}",
                    details=None
                )
            except:
                pass  # Ignore notification errors
            
            return SyncAmazonOrderResponse(
                execution_id=execution_id,
                order_id=order_id,
                success=False,
                error="Validation failed",
                error_details=str(e)
            )
        
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"[{execution_id}] ❌ Unexpected error: {e}",
                exc_info=True
            )
            
            try:
                await self.notification_service.send_error(
                    execution_id=execution_id,
                    order_id=request.amazon_order_id,
                    error=f"Sync failed: {str(e)}",
                    details=str(e)
                )
            except:
                pass  # Ignore notification errors
            
            return SyncAmazonOrderResponse(
                execution_id=execution_id,
                order_id=order_id,
                success=False,
                error="Sync failed",
                error_details=str(e)
            )
    
    async def _maybe_create_snapshot(
        self,
        order: Order,
        execution_id: ExecutionID
    ) -> None:
        """
        Create snapshot if snapshot strategy indicates.
        
        This method is called AFTER events are published and committed.
        It opens a new session to check sequence and create snapshot if needed.
        
        Args:
            order: Order aggregate (with current state)
            execution_id: Execution ID for logging
        """
        try:
            from core.infrastructure.database.event_store import EventStore
            from core.infrastructure.database.config import get_session_factory
            
            # Open new session (events were already committed by Event Bus)
            factory = get_session_factory()
            async with factory() as session:
                try:
                    event_store = EventStore(session)
                    snapshot_store = SnapshotStore(session)
                    
                    # Get current sequence number (from committed events)
                    current_sequence = await event_store.get_latest_sequence(order.order_id.value)
                    
                    if current_sequence == 0:
                        # No events yet, skip snapshot
                        logger.debug(f"[{execution_id}] No events found, skipping snapshot")
                        return
                    
                    # Check if snapshot should be created at current_sequence
                    # OR if we passed a snapshot point (e.g., sequence 5 when interval is 5)
                    should_create = False
                    if hasattr(self.snapshot_strategy, 'event_interval'):
                        # For EventCountSnapshotStrategy: check if we're at or past a snapshot point
                        interval = self.snapshot_strategy.event_interval
                        # Check if current_sequence matches interval OR if we passed it
                        should_create = (current_sequence > 0 and current_sequence % interval == 0)
                        if not should_create and current_sequence > interval:
                            # Check if we passed a snapshot point (e.g., seq 6 when interval is 5)
                            # In this case, create snapshot at the last checkpoint
                            last_checkpoint = (current_sequence // interval) * interval
                            if last_checkpoint > 0 and last_checkpoint < current_sequence:
                                # We passed a checkpoint, create snapshot at that point
                                should_create = await self.snapshot_strategy.should_create_snapshot(
                                    aggregate_id=order.order_id.value,
                                    current_sequence=last_checkpoint,
                                    event_store=event_store
                                )
                                if should_create:
                                    current_sequence = last_checkpoint
                    else:
                        # For other strategies, use normal check
                        should_create = await self.snapshot_strategy.should_create_snapshot(
                            aggregate_id=order.order_id.value,
                            current_sequence=current_sequence,
                            event_store=event_store
                        )
                    
                    if should_create:
                        logger.info(
                            f"[{execution_id}] Creating snapshot for Order "
                            f"{order.order_id.value} (sequence: {current_sequence})"
                        )
                        
                        # Serialize Order state (current state, not rebuilt)
                        snapshot_data = order.to_snapshot_dict()
                        
                        # Save snapshot
                        await snapshot_store.save_snapshot(
                            aggregate_id=order.order_id.value,
                            aggregate_type="Order",
                            snapshot_data=snapshot_data,
                            sequence_number=current_sequence,
                            snapshot_version=1
                        )
                        
                        # Commit snapshot
                        await session.commit()
                        logger.info(
                            f"[{execution_id}] ✅ Snapshot created at sequence {current_sequence}"
                        )
                    else:
                        logger.debug(
                            f"[{execution_id}] Snapshot not needed "
                            f"(sequence: {current_sequence}, interval: {getattr(self.snapshot_strategy, 'event_interval', 'N/A')})"
                        )
                    
                except Exception as e:
                    await session.rollback()
                    raise
        
        except Exception as e:
            # Don't fail the operation if snapshot creation fails
            logger.warning(
                f"[{execution_id}] Failed to create snapshot (non-critical): {e}",
                exc_info=True
            )