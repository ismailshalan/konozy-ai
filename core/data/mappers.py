"""Static mappers for domain entities ↔ database models."""

from decimal import Decimal
from typing import List
from uuid import UUID

from core.domain.entities.order import Order, OrderItem
from core.domain.value_objects import ExecutionID, Money, OrderNumber

from .models.order_model import OrderItemModel, OrderModel


class OrderItemMapper:
    """Static mapper for OrderItem ↔ OrderItemModel transformation."""

    @staticmethod
    def to_domain(model: OrderItemModel) -> OrderItem:
        """Convert ORM model to domain entity.

        Args:
            model: OrderItemModel instance

        Returns:
            OrderItem domain entity
        """
        return OrderItem(
            sku=model.sku,
            title=model.title,
            quantity=model.quantity,
            unit_price=Money(
                amount=Decimal(str(model.unit_price_amount)),
                currency=model.unit_price_currency,
            ),
            total=Money(
                amount=Decimal(str(model.total_amount)),
                currency=model.total_currency,
            ),
        )

    @staticmethod
    def to_persistence(entity: OrderItem, order_id: str) -> OrderItemModel:
        """Convert domain entity to ORM model.

        Args:
            entity: OrderItem domain entity
            order_id: Order ID string

        Returns:
            OrderItemModel instance
        """
        return OrderItemModel(
            order_id=order_id,
            sku=entity.sku,
            title=entity.title,
            quantity=entity.quantity,
            unit_price_amount=float(entity.unit_price.amount),
            unit_price_currency=entity.unit_price.currency,
            total_amount=float(entity.total.amount),
            total_currency=entity.total.currency,
        )


class OrderMapper:
    """Static mapper for Order ↔ OrderModel transformation with nested items."""

    @staticmethod
    def to_domain(model: OrderModel) -> Order:
        """Convert ORM model to domain aggregate (with nested items).

        Args:
            model: OrderModel instance

        Returns:
            Order domain aggregate
        """
        # Map nested items recursively
        items = [OrderItemMapper.to_domain(item_model) for item_model in model.items]

        # Reconstruct value objects
        execution_id = (
            ExecutionID(value=UUID(model.execution_id)) if model.execution_id else None
        )

        return Order(
            order_id=OrderNumber(value=model.order_id),
            purchase_date=model.purchase_date,
            buyer_email=model.buyer_email,
            items=items,
            order_total=Money(
                amount=Decimal(str(model.order_total_amount)),
                currency=model.order_total_currency,
            ),
            order_status=model.order_status,
            execution_id=execution_id,
        )

    @staticmethod
    def to_persistence(entity: Order) -> OrderModel:
        """Convert domain aggregate to ORM model (with nested items).

        Args:
            entity: Order domain aggregate

        Returns:
            OrderModel instance
        """
        # Create parent order model
        order_model = OrderModel(
            order_id=entity.order_id.value,
            purchase_date=entity.purchase_date,
            buyer_email=entity.buyer_email,
            order_total_amount=float(entity.order_total.amount)
            if entity.order_total
            else 0.0,
            order_total_currency=entity.order_total.currency
            if entity.order_total
            else "USD",
            order_status=entity.order_status,
            execution_id=str(entity.execution_id.value) if entity.execution_id else None,
        )

        # Map nested items recursively
        order_model.items = [
            OrderItemMapper.to_persistence(item, entity.order_id.value)
            for item in entity.items
        ]

        return order_model

    @staticmethod
    def update_persistence(entity: Order, model: OrderModel) -> OrderModel:
        """Update existing ORM model from domain entity (for updates).

        Args:
            entity: Order domain aggregate
            model: Existing OrderModel instance

        Returns:
            Updated OrderModel instance
        """
        model.purchase_date = entity.purchase_date
        model.buyer_email = entity.buyer_email
        model.order_total_amount = (
            float(entity.order_total.amount) if entity.order_total else 0.0
        )
        model.order_total_currency = (
            entity.order_total.currency if entity.order_total else "USD"
        )
        model.order_status = entity.order_status
        model.execution_id = (
            str(entity.execution_id.value) if entity.execution_id else None
        )

        # Clear and rebuild items
        model.items.clear()
        model.items = [
            OrderItemMapper.to_persistence(item, entity.order_id.value)
            for item in entity.items
        ]

        return model
