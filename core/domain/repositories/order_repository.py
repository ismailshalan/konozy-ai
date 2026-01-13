"""Repository interfaces for Order aggregate."""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities.order import Order
from ..value_objects import ExecutionID, OrderNumber


class OrderRepository(ABC):
    """Abstract repository for Order aggregate persistence."""

    @abstractmethod
    async def save(self, order: Order, execution_id: ExecutionID) -> None:
        """Persist order aggregate with execution tracing.

        Args:
            order: Order aggregate to persist
            execution_id: ExecutionID for tracing
        """
        pass

    @abstractmethod
    async def find_by_id(self, order_id: OrderNumber) -> Optional[Order]:
        """Retrieve order by unique identifier.

        Args:
            order_id: OrderNumber identifier

        Returns:
            Order if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_all(self, limit: int = 100) -> List[Order]:
        """List orders with pagination.

        Args:
            limit: Maximum number of orders to return

        Returns:
            List of Order aggregates
        """
        pass

    @abstractmethod
    async def exists(self, order_id: OrderNumber) -> bool:
        """Check if order already exists (duplicate prevention).

        Args:
            order_id: OrderNumber identifier

        Returns:
            True if order exists, False otherwise
        """
        pass
