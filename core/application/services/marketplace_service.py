"""Marketplace service for coordinating marketplace integrations."""

from typing import List, Optional

from typing import List, Optional

from core.application.dtos.order_dto import OrderDTO
from core.application.services.order_service import OrderApplicationService
from core.domain.value_objects import ExecutionID
from core.infrastructure.marketplace.amazon.client import AmazonClient
from core.infrastructure.marketplace.amazon.mapper import AmazonOrderMapper


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
        amazon_client: Optional[AmazonClient] = None,
    ) -> None:
        """Initialize marketplace service.

        Args:
            order_service: OrderApplicationService instance
            amazon_client: Optional AmazonClient instance
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

        # Convert Amazon data to domain entity
        order = AmazonOrderMapper.to_domain_order(amazon_order_data, execution_id)

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

        # Authenticate with Amazon
        await self._amazon_client.authenticate()

        # Fetch orders from Amazon
        amazon_orders = await self._amazon_client.fetch_orders(
            created_after=created_after, limit=limit
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
