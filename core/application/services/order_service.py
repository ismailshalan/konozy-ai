"""Application service for Order operations."""

from typing import List, Optional

from core.application.dtos.order_dto import CreateOrderRequest, OrderDTO, OrderItemDTO
from core.data.uow import UnitOfWork, create_uow
from core.domain.entities.order import Order, OrderItem
from core.domain.value_objects import ExecutionID, Money, OrderNumber
from sqlalchemy.ext.asyncio import async_sessionmaker


class OrderApplicationService:
    """
    Application service for orchestrating order operations.

    Responsibilities:
    - Coordinate domain + infrastructure
    - Handle transactions via UoW
    - Propagate ExecutionID for tracing
    - Transform between DTOs and domain entities
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        """Initialize order application service.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self._session_factory = session_factory

    async def create_order(self, request: CreateOrderRequest) -> OrderDTO:
        """Create a new order.

        Args:
            request: CreateOrderRequest DTO

        Returns:
            OrderDTO with created order details
        """
        uow = create_uow(self._session_factory)
        async with uow:
            execution_id = uow.execution_id

            # 1. Check for duplicates
            order_id = OrderNumber(value=request.order_id)
            exists = await uow.orders.exists(order_id)
            if exists:
                # If exists, retrieve and return
                existing_order = await uow.orders.find_by_id(order_id)
                if existing_order:
                    return self._order_to_dto(existing_order)

            # 2. Transform DTO to domain entity
            order = self._dto_to_order(request, execution_id)

            # 3. Apply business rules (recalculate total)
            order._recalculate_total()

            # 4. Persist via repository
            await uow.orders.save(order, execution_id)

            # 5. Atomic commit
            await uow.commit()

            # 6. Return DTO
            return self._order_to_dto(order)

    async def get_order(self, order_id: str) -> Optional[OrderDTO]:
        """Get order by ID.

        Args:
            order_id: Order ID string

        Returns:
            OrderDTO if found, None otherwise
        """
        uow = create_uow(self._session_factory)
        async with uow:
            order_number = OrderNumber(value=order_id)
            order = await uow.orders.find_by_id(order_number)

            if not order:
                return None

            return self._order_to_dto(order)

    async def list_orders(self, limit: int = 100) -> List[OrderDTO]:
        """List orders with pagination.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of OrderDTO instances
        """
        uow = create_uow(self._session_factory)
        async with uow:
            orders = await uow.orders.find_all(limit=limit)
            return [self._order_to_dto(order) for order in orders]

    def _dto_to_order(self, request: CreateOrderRequest, execution_id: ExecutionID) -> Order:
        """Transform CreateOrderRequest DTO to Order domain entity.

        Args:
            request: CreateOrderRequest DTO
            execution_id: ExecutionID for tracing

        Returns:
            Order domain entity
        """
        items = [
            OrderItem(
                sku=item.sku,
                title=item.title,
                quantity=item.quantity,
                unit_price=Money(
                    amount=item.unit_price_amount,
                    currency=item.unit_price_currency,
                ),
                total=Money(
                    amount=item.total_amount,
                    currency=item.total_currency,
                ),
            )
            for item in request.items
        ]

        return Order(
            order_id=OrderNumber(value=request.order_id),
            purchase_date=request.purchase_date,
            buyer_email=request.buyer_email,
            items=items,
            order_status=request.order_status,
            execution_id=execution_id,
        )

    def _order_to_dto(self, order: Order) -> OrderDTO:
        """Transform Order domain entity to OrderDTO.

        Args:
            order: Order domain entity

        Returns:
            OrderDTO instance
        """
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

        return OrderDTO(
            order_id=order.order_id.value,
            purchase_date=order.purchase_date,
            buyer_email=order.buyer_email,
            items=items,
            order_total_amount=order.order_total.amount if order.order_total else 0,
            order_total_currency=order.order_total.currency if order.order_total else "USD",
            order_status=order.order_status,
            execution_id=str(order.execution_id.value) if order.execution_id else None,
        )
