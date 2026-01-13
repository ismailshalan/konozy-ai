"""Application DTOs for Order operations."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderItemDTO(BaseModel):
    """DTO for order item."""

    sku: str = Field(..., description="Product SKU")
    title: str = Field(..., description="Product title")
    quantity: int = Field(..., gt=0, description="Quantity ordered")
    unit_price_amount: Decimal = Field(..., ge=0, description="Unit price amount")
    unit_price_currency: str = Field(default="USD", description="Currency code")
    total_amount: Decimal = Field(..., ge=0, description="Total amount")
    total_currency: str = Field(default="USD", description="Currency code")

    model_config = {"frozen": True}


class CreateOrderRequest(BaseModel):
    """Request DTO for creating an order."""

    order_id: str = Field(..., description="Amazon order ID")
    purchase_date: datetime = Field(..., description="Purchase date")
    buyer_email: str = Field(..., description="Buyer email address")
    items: List[OrderItemDTO] = Field(default_factory=list, description="Order items")
    order_status: str = Field(default="Pending", description="Order status")

    model_config = {"frozen": True}


class OrderDTO(BaseModel):
    """Response DTO for order details."""

    order_id: str = Field(..., description="Amazon order ID")
    purchase_date: datetime = Field(..., description="Purchase date")
    buyer_email: str = Field(..., description="Buyer email address")
    items: List[OrderItemDTO] = Field(default_factory=list, description="Order items")
    order_total_amount: Decimal = Field(..., ge=0, description="Total order amount")
    order_total_currency: str = Field(default="USD", description="Currency code")
    order_status: str = Field(..., description="Order status")
    execution_id: Optional[str] = Field(None, description="Execution ID for tracing")

    model_config = {"frozen": True}


class OrderListDTO(BaseModel):
    """DTO for listing orders."""

    orders: List[OrderDTO] = Field(default_factory=list, description="List of orders")
    total: int = Field(..., ge=0, description="Total count")

    model_config = {"frozen": True}
