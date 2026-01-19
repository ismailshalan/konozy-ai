"""
Order aggregate root.

CRITICAL: This file must contain ZERO imports from:
- sqlalchemy
- pydantic
- fastapi
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from ..value_objects import ExecutionID, Money, OrderNumber
from ..value_objects import FinancialBreakdown, FinancialLine
from ..events.base import DomainEvent


@dataclass
class OrderItem:
    """Individual line item within an order."""
    sku: str
    title: str
    quantity: int
    unit_price: Money
    total: Money

    def calculate_total(self) -> Money:
        """Recalculate total based on quantity and unit price."""
        calculated = Money(
            amount=self.unit_price.amount * self.quantity,
            currency=self.unit_price.currency,
        )
        if calculated != self.total:
            raise ValueError(f"Total mismatch: {calculated} vs {self.total}")
        return calculated


@dataclass
class Order:
    """
    Order aggregate root with financial breakdown.
    
    This is the main domain entity representing a marketplace order
    with complete financial decomposition.
    """
    order_id: OrderNumber
    purchase_date: datetime
    buyer_email: str
    items: List[OrderItem] = field(default_factory=list)
    
    # Financial breakdown (from Amazon Financial Events API)
    financial_breakdown: Optional[FinancialBreakdown] = None
    
    # Metadata
    order_total: Optional[Money] = None
    order_status: str = "Pending"
    execution_id: Optional[ExecutionID] = None
    marketplace: Optional[str] = None  # "amazon", "noon", etc.
    error_message: Optional[str] = None  # For failed syncs
    
    # Event collection (for Event Sourcing)
    _domain_events: List[DomainEvent] = field(default_factory=list, init=False, repr=False)
    
    def __post_init__(self):
        """Record initial events after Order creation."""
        # Record OrderCreatedEvent
        from ..events.order_events import OrderCreatedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        if not execution_id_str and not hasattr(self, '_skip_creation_event'):
            # Generate execution_id if not provided
            if not self.execution_id:
                self.execution_id = ExecutionID.generate()
                execution_id_str = str(self.execution_id.value)
        
        # Only record if not already recorded (e.g., from create() factory)
        if not any(isinstance(e, OrderCreatedEvent) for e in self._domain_events):
            self._record_event(
                OrderCreatedEvent(
                    order_id=str(self.order_id.value),
                    marketplace=self.marketplace or "amazon",
                    buyer_email=self.buyer_email,
                    purchase_date=self.purchase_date.isoformat(),
                    execution_id=execution_id_str,
                )
            )
        
        # Record FinancialsExtractedEvent if financial_breakdown is provided
        if self.financial_breakdown:
            from ..events.order_events import FinancialsExtractedEvent
            
            self._record_event(
                FinancialsExtractedEvent(
                    order_id=str(self.order_id.value),
                    principal_amount=self.financial_breakdown.principal.amount,
                    principal_currency=self.financial_breakdown.principal.currency,
                    net_proceeds=self.financial_breakdown.net_proceeds.amount,
                    financial_lines_count=len(self.financial_breakdown.financial_lines),
                    execution_id=execution_id_str,
                )
            )
    
    def add_item(self, item: OrderItem) -> None:
        """Add item and recalculate order total."""
        self.items.append(item)
        self._recalculate_total()
        self._record_update({"items": "added"})

    def _recalculate_total(self) -> None:
        """Internal: Sum all item totals."""
        if not self.items:
            self.order_total = Money(amount=Decimal("0.00"))
            return

        total = sum(item.total.amount for item in self.items)
        self.order_total = Money(amount=total, currency=self.items[0].total.currency)

    def mark_shipped(self) -> None:
        """Business rule: Transition to shipped status."""
        if self.order_status == "Cancelled":
            raise ValueError("Cannot ship a cancelled order")
        previous_status = self.order_status
        self.order_status = "Shipped"
        self._record_status_change(previous_status, "Shipped", "Order marked as shipped")
    
    def mark_synced(self) -> None:
        """
        Mark order as successfully synced.
        
        Records sync success event.
        """
        self.order_status = "Synced"
        self.error_message = None
        
        from ..events.order_events import OrderSyncedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        principal_amount = None
        net_proceeds = None
        
        if self.financial_breakdown:
            principal_amount = self.financial_breakdown.principal.amount
            net_proceeds = self.financial_breakdown.net_proceeds.amount
        
        self._record_event(
            OrderSyncedEvent(
                order_id=str(self.order_id.value),
                principal_amount=principal_amount,
                net_proceeds=net_proceeds,
                execution_id=execution_id_str,
            )
        )
    
    def mark_failed(self, error_message: str, error_details: Optional[str] = None) -> None:
        """
        Mark order as failed.
        
        Records failure event with error details.
        """
        self.order_status = "Failed"
        self.error_message = error_message
        
        from ..events.order_events import OrderFailedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        self._record_event(
            OrderFailedEvent(
                order_id=str(self.order_id.value),
                error_type="SyncError",
                error_message=error_message,
                error_details=error_details,
                step_failed="unknown",
                execution_id=execution_id_str,
            )
        )
    
    def validate_financials(self) -> None:
        """
        Validate financial breakdown.
        
        Records validation event (success or failure).
        
        Raises:
            ValueError: If financial breakdown missing or invalid
        """
        from ..events.order_events import OrderValidatedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        
        if not self.financial_breakdown:
            error_msg = "No financial breakdown to validate"
            self._record_event(
                OrderValidatedEvent(
                    order_id=str(self.order_id.value),
                    validation_passed=False,
                    validation_message=error_msg,
                    execution_id=execution_id_str,
                )
            )
            raise ValueError(error_msg)
        
        try:
            # Calculate net proceeds from principal and fees
            calculated_net = self.financial_breakdown.principal.amount
            
            for line in self.financial_breakdown.financial_lines:
                calculated_net += line.amount.amount
            
            # Verify balance equation: Principal + Fees = Net Proceeds
            difference = abs(
                calculated_net - self.financial_breakdown.net_proceeds.amount
            )
            
            if difference > Decimal("0.01"):
                error_msg = (
                    f"Financial validation failed: "
                    f"Principal ({self.financial_breakdown.principal.amount}) "
                    f"+ Fees = {calculated_net}, "
                    f"but Net Proceeds = {self.financial_breakdown.net_proceeds.amount}"
                )
                
                # Record validation failure
                self._record_event(
                    OrderValidatedEvent(
                        order_id=str(self.order_id.value),
                        validation_passed=False,
                        validation_message=error_msg,
                        execution_id=execution_id_str,
                    )
                )
                
                raise ValueError(error_msg)
            
            # Record validation success
            self._record_event(
                OrderValidatedEvent(
                    order_id=str(self.order_id.value),
                    validation_passed=True,
                    validation_message="Balance equation verified",
                    execution_id=execution_id_str,
                )
            )
        
        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected validation error: {str(e)}"
            self._record_event(
                OrderValidatedEvent(
                    order_id=str(self.order_id.value),
                    validation_passed=False,
                    validation_message=error_msg,
                    execution_id=execution_id_str,
                )
            )
            raise ValueError(error_msg)
    
    # =========================================================================
    # EVENT COLLECTION (Event Sourcing)
    # =========================================================================
    
    def get_domain_events(self) -> List[DomainEvent]:
        """
        Get all domain events collected by this aggregate.
        
        Returns:
            List of domain events (will be published to Event Bus)
        """
        return list(self._domain_events)
    
    def get_events(self) -> List[DomainEvent]:
        """
        Get all recorded events.
        
        Returns:
            Copy of events list
        """
        return self.get_domain_events()
    
    def clear_domain_events(self) -> None:
        """Clear all collected domain events (after publishing)."""
        self._domain_events.clear()
    
    def clear_events(self) -> None:
        """Clear recorded events after persistence."""
        self.clear_domain_events()
    
    def _record_update(self, updated_fields: dict) -> None:
        """Record OrderUpdatedEvent when order is modified."""
        from ..events.order_events import OrderUpdatedEvent
        
        event = OrderUpdatedEvent(
            order_id=str(self.order_id.value),
            updated_fields=updated_fields,
            execution_id=str(self.execution_id.value) if self.execution_id else None,
        )
        self._domain_events.append(event)
    
    def _record_status_change(self, previous_status: str, new_status: str, reason: Optional[str] = None) -> None:
        """Record OrderStatusChangedEvent when status changes."""
        from ..events.order_events import OrderStatusChangedEvent
        
        event = OrderStatusChangedEvent(
            order_id=str(self.order_id.value),
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            execution_id=str(self.execution_id.value) if self.execution_id else None,
        )
        self._domain_events.append(event)
    
    def _record_event(self, event: DomainEvent) -> None:
        """
        Record domain event.
        
        Args:
            event: Domain event to record
        """
        self._domain_events.append(event)
    
    def record_order_saved(self, database_id: str) -> None:
        """
        Record that order was saved to database.
        
        Args:
            database_id: Database record ID
        """
        from ..events.order_events import OrderSavedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        self._record_event(
            OrderSavedEvent(
                order_id=str(self.order_id.value),
                database_id=database_id,
                execution_id=execution_id_str,
            )
        )
    
    def record_invoice_created(
        self,
        invoice_id: int,
        partner_id: int,
        lines_count: int
    ) -> None:
        """
        Record that invoice was created in Odoo.
        
        Args:
            invoice_id: Odoo invoice ID
            partner_id: Odoo partner ID
            lines_count: Number of invoice lines
        """
        from ..events.order_events import InvoiceCreatedEvent
        
        execution_id_str = str(self.execution_id.value) if self.execution_id else None
        self._record_event(
            InvoiceCreatedEvent(
                order_id=str(self.order_id.value),
                invoice_id=invoice_id,
                partner_id=partner_id,
                invoice_lines_count=lines_count,
                execution_id=execution_id_str,
            )
        )
    
    # =========================================================================
    # SNAPSHOT SUPPORT (Event Sourcing Optimization)
    # =========================================================================
    
    def to_snapshot_dict(self) -> Dict[str, Any]:
        """
        Serialize Order state to dictionary for snapshot storage.
        
        Returns:
            Dictionary containing all Order state
        """
        from decimal import Decimal
        
        snapshot = {
            'order_id': str(self.order_id.value),
            'purchase_date': self.purchase_date.isoformat(),
            'buyer_email': self.buyer_email,
            'order_status': self.order_status,
            'marketplace': self.marketplace,
            'error_message': self.error_message,
            'execution_id': str(self.execution_id.value) if self.execution_id else None,
        }
        
        # Serialize items
        if self.items:
            snapshot['items'] = [
                {
                    'sku': item.sku,
                    'title': item.title,
                    'quantity': item.quantity,
                    'unit_price_amount': str(item.unit_price.amount),
                    'unit_price_currency': item.unit_price.currency,
                    'total_amount': str(item.total.amount),
                    'total_currency': item.total.currency,
                }
                for item in self.items
            ]
        
        # Serialize financial breakdown
        if self.financial_breakdown:
            snapshot['financial_breakdown'] = {
                'principal_amount': str(self.financial_breakdown.principal.amount),
                'principal_currency': self.financial_breakdown.principal.currency,
                'net_proceeds_amount': str(self.financial_breakdown.net_proceeds.amount),
                'net_proceeds_currency': self.financial_breakdown.net_proceeds.currency,
                'financial_lines': [
                    {
                        'line_type': line.line_type,
                        'description': line.description,
                        'amount': str(line.amount.amount),
                        'currency': line.amount.currency,
                        'sku': line.sku,
                    }
                    for line in self.financial_breakdown.financial_lines
                ]
            }
        
        # Serialize order total
        if self.order_total:
            snapshot['order_total_amount'] = str(self.order_total.amount)
            snapshot['order_total_currency'] = self.order_total.currency
        
        return snapshot
    
    @classmethod
    def from_snapshot_dict(cls, snapshot_data: Dict[str, Any]) -> 'Order':
        """
        Restore Order from snapshot dictionary.
        
        Args:
            snapshot_data: Dictionary containing Order state
        
        Returns:
            Restored Order instance
        """
        from decimal import Decimal
        from datetime import datetime
        
        # Restore basic fields
        order = cls(
            order_id=OrderNumber(snapshot_data['order_id']),
            purchase_date=datetime.fromisoformat(snapshot_data['purchase_date']),
            buyer_email=snapshot_data['buyer_email'],
            order_status=snapshot_data.get('order_status', 'Pending'),
            marketplace=snapshot_data.get('marketplace'),
            error_message=snapshot_data.get('error_message'),
            execution_id=ExecutionID(snapshot_data['execution_id']) if snapshot_data.get('execution_id') else None,
        )
        
        # Restore items
        if 'items' in snapshot_data:
            for item_data in snapshot_data['items']:
                item = OrderItem(
                    sku=item_data['sku'],
                    title=item_data['title'],
                    quantity=item_data['quantity'],
                    unit_price=Money(
                        amount=Decimal(item_data['unit_price_amount']),
                        currency=item_data['unit_price_currency']
                    ),
                    total=Money(
                        amount=Decimal(item_data['total_amount']),
                        currency=item_data['total_currency']
                    )
                )
                order.items.append(item)
        
        # Restore financial breakdown
        if 'financial_breakdown' in snapshot_data:
            fb_data = snapshot_data['financial_breakdown']
            financial_lines = []
            
            for line_data in fb_data.get('financial_lines', []):
                line = FinancialLine(
                    line_type=line_data['line_type'],
                    description=line_data['description'],
                    amount=Money(
                        amount=Decimal(line_data['amount']),
                        currency=line_data['currency']
                    ),
                    sku=line_data.get('sku')
                )
                financial_lines.append(line)
            
            order.financial_breakdown = FinancialBreakdown(
                principal=Money(
                    amount=Decimal(fb_data['principal_amount']),
                    currency=fb_data['principal_currency']
                ),
                financial_lines=financial_lines,
                net_proceeds=Money(
                    amount=Decimal(fb_data['net_proceeds_amount']),
                    currency=fb_data['net_proceeds_currency']
                )
            )
        
        # Restore order total
        if 'order_total_amount' in snapshot_data:
            order.order_total = Money(
                amount=Decimal(snapshot_data['order_total_amount']),
                currency=snapshot_data['order_total_currency']
            )
        
        # Clear events (snapshot is a clean state)
        order.clear_events()
        
        return order
    
    @classmethod
    def create(
        cls,
        order_id: OrderNumber,
        purchase_date: datetime,
        buyer_email: str,
        marketplace: str,
        execution_id: Optional[ExecutionID] = None,
    ) -> 'Order':
        """
        Factory method to create a new Order.
        
        This method publishes OrderCreatedEvent automatically.
        
        Args:
            order_id: Order identifier
            purchase_date: Date of purchase
            buyer_email: Buyer email address
            marketplace: Marketplace name (e.g., "amazon")
            execution_id: Optional execution ID for tracing
        
        Returns:
            New Order instance with OrderCreatedEvent collected
        """
        from ..events.order_events import OrderCreatedEvent
        
        # Generate execution_id if not provided
        if not execution_id:
            execution_id = ExecutionID.generate()
        
        order = cls(
            order_id=order_id,
            purchase_date=purchase_date,
            buyer_email=buyer_email,
            marketplace=marketplace,
            execution_id=execution_id,
            order_status="Pending",
        )
        
        # Note: OrderCreatedEvent will be recorded in __post_init__
        # But we need to ensure it's not duplicated, so we'll let __post_init__ handle it
        
        return order