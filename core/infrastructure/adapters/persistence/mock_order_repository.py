"""
Mock Order Repository Implementation.

This is an in-memory implementation for testing and demos.
"""
from typing import Optional, List, Dict
import logging

from core.domain.entities.order import Order
from core.domain.value_objects import OrderNumber, ExecutionID
from core.domain.repositories.order_repository import OrderRepository


logger = logging.getLogger(__name__)


class MockOrderRepository(OrderRepository):
    """
    In-memory implementation of OrderRepository.
    
    Stores orders in a dictionary for testing/demo purposes.
    """
    
    def __init__(self):
        """Initialize empty storage."""
        self._storage: Dict[str, Order] = {}
        logger.info("MockOrderRepository initialized (in-memory storage)")
    
    async def save(self, order: Order, execution_id: ExecutionID) -> None:
        """
        Save order to in-memory storage.
        
        Args:
            order: Order entity to save
            execution_id: Execution ID for tracing
        """
        self._storage[order.order_id.value] = order
        logger.info(
            f"✅ Order saved to mock repository: {order.order_id.value} "
            f"(status: {order.order_status}, execution_id: {execution_id.value})"
        )
    
    async def find_by_id(self, order_id: OrderNumber) -> Optional[Order]:
        """
        Get order by ID from in-memory storage.
        
        Args:
            order_id: Order ID to lookup
        
        Returns:
            Order if found, None otherwise
        """
        order = self._storage.get(order_id.value)
        
        if order:
            logger.info(f"✅ Order found in mock repository: {order_id.value}")
        else:
            logger.info(f"❌ Order not found in mock repository: {order_id.value}")
        
        return order
    
    async def get_by_id(self, order_id: OrderNumber) -> Optional[Order]:
        """Alias for find_by_id (for compatibility)."""
        return await self.find_by_id(order_id)
    
    async def find_all(self, limit: int = 100) -> List[Order]:
        """
        Get all orders with pagination.
        
        Args:
            limit: Maximum number of orders to return
        
        Returns:
            List of orders (up to limit)
        """
        orders = list(self._storage.values())[:limit]
        logger.info(f"Found {len(orders)} order(s) in mock repository (limit: {limit})")
        return orders
    
    async def exists(self, order_id: OrderNumber) -> bool:
        """
        Check if order exists in storage.
        
        Args:
            order_id: Order ID to check
        
        Returns:
            True if exists, False otherwise
        """
        exists = order_id.value in self._storage
        logger.debug(f"Order {order_id.value} exists: {exists}")
        return exists
    
    async def delete(self, order_id: OrderNumber) -> None:
        """
        Delete order from in-memory storage.
        
        Args:
            order_id: Order ID to delete
        """
        if order_id.value in self._storage:
            del self._storage[order_id.value]
            logger.info(f"✅ Order deleted from mock repository: {order_id.value}")
        else:
            logger.warning(f"⚠️ Order not found for deletion: {order_id.value}")
    
    def get_all(self) -> List[Order]:
        """
        Get all orders (for demo/testing).
        
        Returns:
            List of all orders
        """
        return list(self._storage.values())
    
    def clear(self) -> None:
        """Clear all orders (for demo/testing)."""
        self._storage.clear()
        logger.info("🗑️ Mock repository cleared")
