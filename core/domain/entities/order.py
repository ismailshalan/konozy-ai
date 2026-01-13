"""Domain entities - Order and OrderItem."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List

from ..value_objects import ExecutionID, Money, OrderNumber


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
    """Aggregate root for Amazon order domain."""

    order_id: OrderNumber
    purchase_date: datetime
    buyer_email: str
    items: List[OrderItem] = field(default_factory=list)
    order_total: Money | None = None
    order_status: str = "Pending"
    execution_id: ExecutionID | None = None

    def add_item(self, item: OrderItem) -> None:
        """Add item and recalculate order total."""
        self.items.append(item)
        self._recalculate_total()

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
        self.order_status = "Shipped"
