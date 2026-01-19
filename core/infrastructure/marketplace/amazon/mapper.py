"""Amazon SP-API to Domain Entity mapper."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from core.domain.entities.order import Order, OrderItem
from core.domain.value_objects import ExecutionID, Money, OrderNumber


class AmazonOrderMapper:
    """Mapper for converting Amazon SP-API JSON to Domain Order Entity."""

    @staticmethod
    def to_domain_order(amazon_data: Dict[str, Any], execution_id: ExecutionID) -> Order:
        """Convert Amazon SP-API order data to Domain Order Entity.

        Args:
            amazon_data: Raw JSON data from Amazon SP-API
            execution_id: ExecutionID for tracing

        Returns:
            Order domain entity

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Extract order ID
        order_id_str = amazon_data.get("AmazonOrderId") or amazon_data.get("OrderId")
        if not order_id_str:
            raise ValueError("Amazon order data must contain 'AmazonOrderId' or 'OrderId'")

        # Extract purchase date
        purchase_date_str = amazon_data.get("PurchaseDate")
        if not purchase_date_str:
            raise ValueError("Amazon order data must contain 'PurchaseDate'")

        # Parse purchase date (Amazon format: ISO 8601)
        try:
            # Handle different date formats from Amazon
            if isinstance(purchase_date_str, str):
                # Remove timezone info if present, then parse
                purchase_date_str = purchase_date_str.replace("Z", "+00:00")
                purchase_date = datetime.fromisoformat(purchase_date_str.replace("Z", "+00:00"))
            else:
                purchase_date = purchase_date_str
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid purchase date format: {purchase_date_str}") from e

        # Extract buyer email
        buyer_info = amazon_data.get("BuyerInfo", {})
        buyer_email = buyer_info.get("BuyerEmail") or amazon_data.get("BuyerEmail", "")

        # Extract order status
        order_status = amazon_data.get("OrderStatus", "Pending")

        # Map order items
        items = []
        order_items_data = amazon_data.get("OrderItems", []) or amazon_data.get("Items", [])

        for item_data in order_items_data:
            order_item = AmazonOrderMapper._map_order_item(item_data)
            items.append(order_item)

        # Create order entity
        order = Order(
            order_id=OrderNumber(value=order_id_str),
            purchase_date=purchase_date,
            buyer_email=buyer_email,
            items=items,
            order_status=order_status,
            execution_id=execution_id,
        )

        # Recalculate total to ensure consistency
        order._recalculate_total()

        return order

    @staticmethod
    def _map_order_item(item_data: Dict[str, Any]) -> OrderItem:
        """Convert Amazon order item data to OrderItem entity.

        Args:
            item_data: Amazon order item JSON data

        Returns:
            OrderItem domain entity

        Raises:
            ValueError: If required fields are missing
        """
        # Extract SKU
        sku = item_data.get("SellerSKU") or item_data.get("SKU") or item_data.get("Asin", "")

        # Extract title
        title = item_data.get("Title") or item_data.get("ProductInfo", {}).get("Title", "")

        # Extract quantity
        quantity = int(item_data.get("QuantityOrdered", item_data.get("Quantity", 1)))

        # Extract price information
        price_info = item_data.get("ItemPrice", {}) or item_data.get("Price", {})
        
        # Handle different price formats
        if isinstance(price_info, dict):
            amount_str = price_info.get("Amount") or price_info.get("Value", "0.00")
            currency = price_info.get("CurrencyCode") or price_info.get("Currency", "USD")
        else:
            amount_str = str(price_info) if price_info else "0.00"
            currency = "USD"

        # Convert amount to Decimal
        try:
            unit_price_amount = Decimal(str(amount_str))
        except (ValueError, TypeError):
            unit_price_amount = Decimal("0.00")

        # Create Money value objects
        unit_price = Money(amount=unit_price_amount, currency=currency)
        total = Money(amount=unit_price_amount * quantity, currency=currency)

        return OrderItem(
            sku=sku,
            title=title,
            quantity=quantity,
            unit_price=unit_price,
            total=total,
        )
