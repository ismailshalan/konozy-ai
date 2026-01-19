"""
SQLAlchemy ORM Models.

Maps domain entities to database tables.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, String, DateTime, Integer, Numeric, BigInteger,
    Text, Boolean, Index, ForeignKey, func, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid


Base = declarative_base()


# =============================================================================
# ORDER MODEL
# =============================================================================

class OrderModel(Base):
    """
    Order database model.
    
    Stores order information with financial data.
    """
    
    __tablename__ = "orders"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Order identifiers
    order_id = Column(String(255), unique=True, nullable=False, index=True)
    execution_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Order metadata
    marketplace = Column(String(50), nullable=False, index=True)
    purchase_date = Column(DateTime, nullable=False)
    buyer_email = Column(String(255), nullable=True)
    
    # Order status
    order_status = Column(String(50), nullable=False, default="Pending", index=True)
    error_message = Column(Text, nullable=True)
    
    # Financial data (denormalized for performance)
    principal_amount = Column(Numeric(15, 2), nullable=True)
    principal_currency = Column(String(3), nullable=True)
    net_proceeds_amount = Column(Numeric(15, 2), nullable=True)
    net_proceeds_currency = Column(String(3), nullable=True)
    
    # Full financial breakdown (stored as JSON)
    financial_breakdown = Column(JSON, nullable=True)
    
    # Odoo integration
    odoo_invoice_id = Column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Soft delete
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    items = relationship("OrderItemModel", back_populates="order", cascade="all, delete-orphan")
    financial_lines = relationship("FinancialLineModel", back_populates="order", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_orders_marketplace_status', 'marketplace', 'order_status'),
        Index('ix_orders_purchase_date', 'purchase_date'),
        Index('ix_orders_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<OrderModel(id={self.id}, order_id={self.order_id}, status={self.order_status})>"


# =============================================================================
# ORDER ITEM MODEL
# =============================================================================

class OrderItemModel(Base):
    """
    Order item database model.
    
    Stores individual items in an order (for multi-SKU support).
    """
    
    __tablename__ = "order_items"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    
    # Item details
    sku = Column(String(255), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    
    # Item financials
    principal_amount = Column(Numeric(15, 2), nullable=False)
    principal_currency = Column(String(3), nullable=False)
    
    # Product metadata
    product_name = Column(String(500), nullable=True)
    odoo_product_id = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    order = relationship("OrderModel", back_populates="items")
    
    def __repr__(self):
        return f"<OrderItemModel(id={self.id}, sku={self.sku}, quantity={self.quantity})>"


# =============================================================================
# FINANCIAL LINE MODEL
# =============================================================================

class FinancialLineModel(Base):
    """
    Financial line database model.
    
    Stores individual fee/charge lines (commission, FBA fees, etc.).
    """
    
    __tablename__ = "financial_lines"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign key
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    
    # Line details
    line_type = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    
    # Amount
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    
    # Associated SKU (if applicable)
    sku = Column(String(255), nullable=True)
    
    # Odoo mapping
    odoo_account_id = Column(Integer, nullable=True)
    odoo_analytic_id = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    order = relationship("OrderModel", back_populates="financial_lines")
    
    # Indexes
    __table_args__ = (
        Index('ix_financial_lines_type', 'line_type'),
    )
    
    def __repr__(self):
        return f"<FinancialLineModel(id={self.id}, type={self.line_type}, amount={self.amount})>"


# =============================================================================
# EVENT STORE MODEL (for Event Sourcing - Phase 2)
# =============================================================================

class EventModel(Base):
    """
    Event store model.
    
    Stores domain events for event sourcing and audit trail.
    Append-only storage for immutable event records.
    """
    
    __tablename__ = "events"
    
    # Primary key - BigInteger auto-increment for global ordering
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event identifier (unique, indexed)
    event_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    
    # Event metadata
    event_type = Column(String(100), nullable=False, index=True)
    event_version = Column(Integer, nullable=False, default=1)
    
    # Aggregate information
    aggregate_id = Column(String(255), nullable=False, index=True)
    aggregate_type = Column(String(100), nullable=False, index=True)
    
    # Event data (flexible JSON schema)
    event_data = Column(JSON, nullable=False)
    
    # Execution context (1.3 Execution-ID Architecture)
    execution_id = Column(UUID(as_uuid=True), nullable=True)
    user_id = Column(String(255), nullable=True)
    
    # Timestamp (server default for consistency)
    occurred_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Sequence number (for per-aggregate ordering)
    sequence_number = Column(Integer, nullable=False)
    
    # Additional metadata (JSON for flexibility)
    event_metadata = Column("metadata", JSON, nullable=True)
    
    # Indexes (critical for performance)
    __table_args__ = (
        # Composite index for aggregate event queries
        Index('ix_events_aggregate_sequence', 'aggregate_id', 'sequence_number'),
        # Composite index for aggregate type queries
        Index('ix_events_aggregate_type_occurred', 'aggregate_type', 'occurred_at'),
        # Composite index for event type queries
        Index('ix_events_event_type_occurred', 'event_type', 'occurred_at'),
        # Index for execution queries
        Index('ix_events_execution_id', 'execution_id'),
        # Unique constraint for optimistic locking
        UniqueConstraint('aggregate_id', 'sequence_number', name='ix_events_aggregate_unique_sequence'),
    )
    
    def __repr__(self):
        return f"<EventModel(id={self.id}, event_id={self.event_id}, type={self.event_type}, aggregate={self.aggregate_id}, sequence={self.sequence_number})>"


# =============================================================================
# SNAPSHOT MODEL (for Event Sourcing Optimization)
# =============================================================================

class SnapshotModel(Base):
    """
    Snapshot model for Event Sourcing optimization.
    
    Stores aggregate state snapshots to avoid replaying all events.
    Snapshots are created periodically (e.g., every N events or time-based).
    """
    
    __tablename__ = "snapshots"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Aggregate information
    aggregate_id = Column(String(255), nullable=False, index=True)
    aggregate_type = Column(String(100), nullable=False, index=True)
    
    # Snapshot data (JSON - stores complete aggregate state)
    snapshot_data = Column(JSON, nullable=False)
    
    # Snapshot metadata
    snapshot_version = Column(Integer, nullable=False, default=1)
    sequence_number = Column(Integer, nullable=False)  # Last event sequence included in snapshot
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        # Composite index for aggregate snapshot queries
        Index('ix_snapshots_aggregate_sequence', 'aggregate_id', 'sequence_number'),
        # Index for latest snapshot queries
        Index('ix_snapshots_aggregate_created', 'aggregate_id', 'created_at'),
        # Unique constraint: one snapshot per aggregate per sequence
        UniqueConstraint('aggregate_id', 'sequence_number', name='ix_snapshots_aggregate_unique_sequence'),
    )
    
    def __repr__(self):
        return f"<SnapshotModel(id={self.id}, aggregate={self.aggregate_id}, sequence={self.sequence_number}, version={self.snapshot_version})>"
