"""
Unit of Work Pattern Implementation.

Manages database transactions and repository lifecycle.
"""
from typing import Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from core.infrastructure.database.repositories import SQLAlchemyOrderRepository


logger = logging.getLogger(__name__)


class UnitOfWork:
    """
    Unit of Work pattern implementation.
    
    Manages database session lifecycle and transactions.
    Provides access to repositories within a transaction context.
    
    Usage:
        async with UnitOfWork(session) as uow:
            order = await uow.orders.get_by_id(order_id)
            order.mark_synced()
            await uow.orders.save(order, execution_id)
            await uow.commit()
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Unit of Work.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._orders: Optional[SQLAlchemyOrderRepository] = None
    
    async def __aenter__(self):
        """Enter async context."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit async context.
        
        Rolls back transaction if exception occurred.
        """
        if exc_type is not None:
            logger.error(f"Transaction failed: {exc_val}")
            await self.rollback()
        
        # Don't close session here - it's managed externally
    
    @property
    def orders(self) -> SQLAlchemyOrderRepository:
        """
        Get order repository.
        
        Returns:
            Order repository instance
        """
        if self._orders is None:
            self._orders = SQLAlchemyOrderRepository(self.session)
        
        return self._orders
    
    async def commit(self):
        """Commit transaction."""
        try:
            await self.session.commit()
            logger.info("✅ Transaction committed")
        except Exception as e:
            logger.error(f"❌ Commit failed: {e}")
            await self.rollback()
            raise
    
    async def rollback(self):
        """Rollback transaction."""
        await self.session.rollback()
        logger.warning("Transaction rolled back")
