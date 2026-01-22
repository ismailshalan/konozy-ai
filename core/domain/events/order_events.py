"""
Order Domain Events.

Events that occur during order lifecycle in 3.1 Order Pipeline.

Architecture Integration:
- Published to 1.1 Event Bus
- Stored in Event Store
- Tracked by 1.3 Execution-ID
- Consumed by agents in 4.0 and 5.0
"""
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

from .base import DomainEvent


@dataclass
class OrderCreatedEvent(DomainEvent):
    """
    Order was created in the system.
    
    Pipeline: 3.1 Order Pipeline
    Trigger: New order ingested from marketplace
    Consumers: Control Agent, Notification Agent
    """
    
    order_id: str = ""
    marketplace: str = ""
    buyer_email: str = ""
    purchase_date: str = ""
    
    def __post_init__(self):
        """Set aggregate_id to order_id."""
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderUpdatedEvent(DomainEvent):
    """
    Order was updated.
    
    Triggered when order properties change (items, financials, metadata).
    Used for state rebuilding in Event Sourcing.
    """
    
    order_id: str = ""
    updated_fields: dict = None  # Dictionary of changed fields
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    
    def __post_init__(self):
        """Set aggregate_id to order_id."""
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        if self.updated_fields is None:
            object.__setattr__(self, 'updated_fields', {})
        super().__post_init__()


@dataclass
class OrderStatusChangedEvent(DomainEvent):
    """
    Order status changed.
    
    Tracks status transitions (Pending -> Shipped -> Synced, etc.).
    Critical for workflow tracking and state rebuilding.
    """
    
    order_id: str = ""
    previous_status: str = ""
    new_status: str = ""
    reason: Optional[str] = None
    
    def __post_init__(self):
        """Set aggregate_id to order_id."""
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderFetchedEvent(DomainEvent):
    """
    Order was fetched from marketplace API.
    
    Pipeline: 3.1 Order Pipeline
    Trigger: Order fetched from Amazon SP-API
    Next: Order mapping and validation
    """
    
    order_id: str = ""
    marketplace: str = ""
    buyer_email: str = ""
    purchase_date: str = ""
    
    def __post_init__(self):
        """Set aggregate_id to order_id."""
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class FinancialsExtractedEvent(DomainEvent):
    """
    Financial data extracted from marketplace API.
    
    Pipeline: 3.3 Finance Pipeline
    Agent: Amazon Order Agent (4.1)
    Next: OrderValidatedEvent
    """
    
    order_id: str = ""
    principal_amount: Optional[Decimal] = None
    principal_currency: str = ""
    net_proceeds: Optional[Decimal] = None
    financial_lines_count: int = 0
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderValidatedEvent(DomainEvent):
    """
    Order financials validated.
    
    Validation: Principal - Fees = Net Proceeds
    Critical: Financial accuracy 100%
    Next: OrderSavedEvent or OrderFailedEvent
    """
    
    order_id: str = ""
    validation_passed: bool = True
    validation_message: str = ""
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderSavedEvent(DomainEvent):
    """
    Order persisted to database.
    
    Infrastructure: PostgreSQL
    Next: InvoiceCreatedEvent (if Odoo integration enabled)
    """
    
    order_id: str = ""
    database_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class InvoiceCreatedEvent(DomainEvent):
    """
    Invoice created in Odoo ERP.
    
    Integration: 9.0 Odoo ERP Integration
    System: Odoo ERP (external)
    Next: OrderSyncedEvent
    """
    
    order_id: str = ""
    invoice_id: int = 0
    partner_id: int = 0
    invoice_lines_count: int = 0
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderSyncedEvent(DomainEvent):
    """
    Order sync completed successfully.
    
    Final success event in workflow.
    Consumers: Dashboard, Notification Agent, Analytics
    """
    
    order_id: str = ""
    invoice_id: Optional[int] = None
    principal_amount: Optional[Decimal] = None
    net_proceeds: Optional[Decimal] = None
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class OrderFailedEvent(DomainEvent):
    """
    Order sync failed.
    
    Contains error information for debugging.
    Consumers: Error Handler, Notification Agent, Retry Agent
    """
    
    order_id: str = ""
    error_type: str = ""
    error_message: str = ""
    error_details: Optional[str] = None
    step_failed: str = ""
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class NotificationSentEvent(DomainEvent):
    """
    Notification sent (success or error).
    
    Integration: 10.4 Telegram Notifications
    Channels: Telegram, Email, Webhook
    """
    
    order_id: str = ""
    notification_type: str = ""  # success, error, warning
    channel: str = ""  # telegram, email, webhook
    success: bool = True
    
    def __post_init__(self):
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()


@dataclass
class SyncStartedEvent(DomainEvent):
    """
    Sync run started.
    
    Pipeline: 3.1 Order Pipeline
    Trigger: sync_orders() called
    Contains: execution_id, marketplace, date range
    """
    
    marketplace: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    def __post_init__(self):
        """Set aggregate_id to execution_id for sync-level events."""
        if not self.aggregate_id and self.execution_id:
            object.__setattr__(self, 'aggregate_id', f"sync-{self.execution_id}")
        super().__post_init__()


@dataclass
class SyncCompletedEvent(DomainEvent):
    """
    Sync run completed.
    
    Pipeline: 3.1 Order Pipeline
    Trigger: sync_orders() finished
    Contains: execution_id, summary statistics
    """
    
    marketplace: str = ""
    total_orders: int = 0
    successful: int = 0
    failed: int = 0
    invoices_created: int = 0
    invoices_failed: int = 0
    
    def __post_init__(self):
        """Set aggregate_id to execution_id for sync-level events."""
        if not self.aggregate_id and self.execution_id:
            object.__setattr__(self, 'aggregate_id', f"sync-{self.execution_id}")
        super().__post_init__()


@dataclass
class InvoiceFailedEvent(DomainEvent):
    """
    Invoice creation failed for an order.
    
    Pipeline: 3.1 Order Pipeline
    Trigger: Odoo invoice creation error
    Contains: order_id, error message, execution_id
    """
    
    order_id: str = ""
    error_message: str = ""
    error_type: str = "invoice_creation"
    
    def __post_init__(self):
        """Set aggregate_id to order_id."""
        if not self.aggregate_id and self.order_id:
            object.__setattr__(self, 'aggregate_id', self.order_id)
        super().__post_init__()
