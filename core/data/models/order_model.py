"""SQLAlchemy ORM models for Order aggregate."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from .base import Base


class OrderModel(Base):
    """SQLAlchemy ORM model for orders table."""

    __tablename__ = "orders"

    order_id = Column(String(50), primary_key=True)
    purchase_date = Column(DateTime, nullable=False)
    buyer_email = Column(String(255), nullable=False)
    order_total_amount = Column(Numeric(10, 2), nullable=False)
    order_total_currency = Column(String(3), default="USD")
    order_status = Column(String(50), default="Pending")
    execution_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to items
    items = relationship(
        "OrderItemModel", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItemModel(Base):
    """SQLAlchemy ORM model for order_items table."""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False)
    sku = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price_amount = Column(Numeric(10, 2), nullable=False)
    unit_price_currency = Column(String(3), default="USD")
    total_amount = Column(Numeric(10, 2), nullable=False)
    total_currency = Column(String(3), default="USD")

    # Relationship back to order
    order = relationship("OrderModel", back_populates="items")
