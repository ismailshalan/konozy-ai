"""Marketplace service for coordinating marketplace integrations."""

from typing import List, Optional

from typing import List, Optional

from core.application.dtos.order_dto import OrderDTO
from core.application.services.order_service import OrderApplicationService
from core.domain.value_objects import ExecutionID
from konozy_sdk.amazon.client import AmazonAPI
from konozy_sdk.amazon.orders import AmazonOrderParser as AmazonOrderMapper


class MarketplaceService:
    """Service for coordinating marketplace integrations with order processing.

    Responsibilities:
    - Coordinate between marketplace clients (Amazon, etc.) and OrderApplicationService
    - Transform marketplace data to domain entities
    - Handle marketplace-specific error handling
    - Manage execution tracing across marketplace operations
    """

    def __init__(
        self,
        order_service: OrderApplicationService,
        amazon_client: Optional[AmazonAPI] = None,
    ) -> None:
        """Initialize marketplace service.

        Args:
            order_service: OrderApplicationService instance
            amazon_client: Optional AmazonAPI instance
        """
        self._order_service = order_service
        self._amazon_client = amazon_client

    async def sync_amazon_order(self, amazon_order_data: dict) -> OrderDTO:
        """Sync an Amazon order into the system.

        Args:
            amazon_order_data: Raw order data from Amazon SP-API

        Returns:
            OrderDTO with synced order details

        Raises:
            ValueError: If order data is invalid
            Exception: If sync operation fails
        """
        # Generate execution ID for this sync operation
        execution_id = ExecutionID.generate()

        # Convert Amazon data to domain entity using SDK
        from konozy_sdk.amazon.orders import AmazonOrderParser
        from core.domain.entities.order import Order, OrderItem
        from core.domain.value_objects import OrderNumber, Money
        from datetime import datetime
        from decimal import Decimal
        
        # Extract order data
        amazon_order_id = amazon_order_data.get("AmazonOrderId")
        if not amazon_order_id:
            raise ValueError("AmazonOrderId is required")
        
        purchase_date_str = amazon_order_data.get("PurchaseDate")
        if not purchase_date_str:
            raise ValueError("PurchaseDate is required")
        
        # Parse purchase date
        try:
            purchase_date = datetime.fromisoformat(purchase_date_str.replace("Z", "+00:00"))
        except Exception:
            purchase_date = datetime.utcnow()
        
        buyer_email = amazon_order_data.get("BuyerInfo", {}).get("BuyerEmail")
        order_status = amazon_order_data.get("OrderStatus", "Pending")
        
        # Extract order total
        order_total = None
        if "OrderTotal" in amazon_order_data:
            total_dict = amazon_order_data["OrderTotal"]
            order_total = Money(
                amount=Decimal(str(total_dict.get("Amount", "0.00"))),
                currency=total_dict.get("CurrencyCode", "EGP")
            )
        
        # Extract order items
        items = []
        order_items = amazon_order_data.get("OrderItems", [])
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
        
        # Create Order entity
        order = Order(
            order_id=OrderNumber(value=amazon_order_id),
            purchase_date=purchase_date,
            buyer_email=buyer_email or "",
            items=items,
            order_total=order_total,
            order_status=order_status,
            execution_id=execution_id,
            marketplace="amazon",
        )

        # Use OrderApplicationService to persist
        # Note: We need to convert domain entity back to DTO format for the service
        # This is a temporary approach - in a more refined implementation,
        # we might want to add a method that accepts domain entities directly
        
        from core.application.dtos.order_dto import CreateOrderRequest, OrderItemDTO

        # Convert domain entity to CreateOrderRequest
        create_request = self._order_to_create_request(order)

        # Create order via application service
        return await self._order_service.create_order(create_request)

    async def sync_amazon_orders_batch(
        self, amazon_orders_data: List[dict]
    ) -> List[OrderDTO]:
        """Sync multiple Amazon orders into the system.

        Args:
            amazon_orders_data: List of raw order data from Amazon SP-API

        Returns:
            List of OrderDTO instances for synced orders
        """
        results = []
        for amazon_order_data in amazon_orders_data:
            try:
                order_dto = await self.sync_amazon_order(amazon_order_data)
                results.append(order_dto)
            except Exception as e:
                # Log error and continue with next order
                # In production, you might want to collect errors and return them
                print(f"Error syncing order: {e}")
                continue
        return results

    async def fetch_and_sync_amazon_orders(
        self, created_after: Optional[str] = None, limit: int = 100
    ) -> List[OrderDTO]:
        """Fetch orders from Amazon and sync them into the system.

        Args:
            created_after: ISO 8601 date string for filtering orders
            limit: Maximum number of orders to fetch

        Returns:
            List of OrderDTO instances for synced orders

        Raises:
            RuntimeError: If Amazon client is not configured
        """
        if not self._amazon_client:
            raise RuntimeError("Amazon client is not configured")

        # Fetch orders from Amazon using SDK (sync method, wrap in executor)
        import asyncio
        from datetime import datetime, timedelta
        
        # Calculate created_before if not provided
        if created_after:
            created_after_dt = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            created_before_dt = created_after_dt + timedelta(days=1)
            created_before = created_before_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            created_before = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        loop = asyncio.get_event_loop()
        amazon_orders = await loop.run_in_executor(
            None,
            lambda: self._amazon_client.get_orders(
                created_after=created_after or "",
                created_before=created_before
            )
        )

        # Sync orders
        return await self.sync_amazon_orders_batch(amazon_orders)

    def _order_to_create_request(self, order) -> "CreateOrderRequest":
        """Convert domain Order entity to CreateOrderRequest DTO.

        Args:
            order: Order domain entity

        Returns:
            CreateOrderRequest DTO
        """
        from core.application.dtos.order_dto import CreateOrderRequest, OrderItemDTO

        items = [
            OrderItemDTO(
                sku=item.sku,
                title=item.title,
                quantity=item.quantity,
                unit_price_amount=item.unit_price.amount,
                unit_price_currency=item.unit_price.currency,
                total_amount=item.total.amount,
                total_currency=item.total.currency,
            )
            for item in order.items
        ]

        return CreateOrderRequest(
            order_id=order.order_id.value,
            purchase_date=order.purchase_date,
            buyer_email=order.buyer_email,
            items=items,
            order_status=order.order_status,
        )
