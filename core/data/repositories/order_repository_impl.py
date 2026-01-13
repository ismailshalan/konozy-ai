"""SQLAlchemy implementation of OrderRepository."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.entities.order import Order
from core.domain.repositories.order_repository import OrderRepository
from core.domain.value_objects import ExecutionID, OrderNumber

from ..mappers import OrderMapper
from ..models.order_model import OrderModel


class SqlAlchemyOrderRepository(OrderRepository):
    """Concrete implementation of OrderRepository using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with SQLAlchemy session.

        Args:
            session: SQLAlchemy async session
        """
        self._session = session

    async def save(self, order: Order, execution_id: ExecutionID) -> None:
        """Persist order aggregate with execution tracing.

        Args:
            order: Order domain aggregate
            execution_id: ExecutionID for tracing
        """
        # Check if exists (upsert logic)
        existing = await self._session.get(OrderModel, order.order_id.value)

        if existing:
            # Update existing
            OrderMapper.update_persistence(order, existing)
            self._session.add(existing)
        else:
            # Insert new
            order_model = OrderMapper.to_persistence(order)
            self._session.add(order_model)

        await self._session.flush()  # Propagate to DB without committing

    async def find_by_id(self, order_id: OrderNumber) -> Optional[Order]:
        """Retrieve order by unique identifier.

        Args:
            order_id: OrderNumber identifier

        Returns:
            Order if found, None otherwise
        """
        result = await self._session.execute(
            select(OrderModel).where(OrderModel.order_id == order_id.value)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        return OrderMapper.to_domain(model)

    async def find_all(self, limit: int = 100) -> List[Order]:
        """List orders with pagination.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of Order aggregates
        """
        result = await self._session.execute(select(OrderModel).limit(limit))
        models = result.scalars().all()

        return [OrderMapper.to_domain(model) for model in models]

    async def exists(self, order_id: OrderNumber) -> bool:
        """Check if order already exists (duplicate prevention).

        Args:
            order_id: OrderNumber identifier

        Returns:
            True if order exists, False otherwise
        """
        result = await self._session.execute(
            select(OrderModel.order_id).where(OrderModel.order_id == order_id.value)
        )
        return result.scalar_one_or_none() is not None
