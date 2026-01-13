"""Unit of Work pattern for atomic transactions."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.domain.value_objects import ExecutionID

from .repositories.order_repository_impl import SqlAlchemyOrderRepository


class UnitOfWork:
    """
    Unit of Work pattern for atomic transactions.

    Responsibilities:
    1. Manage SQLAlchemy session lifecycle
    2. Propagate ExecutionID across all operations
    3. Atomic commit/rollback of all repository operations
    4. Lazy initialization of repositories
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        """Initialize Unit of Work.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._execution_id: Optional[ExecutionID] = None

        # Lazy-loaded repositories
        self._order_repository: Optional[SqlAlchemyOrderRepository] = None

    async def __aenter__(self) -> "UnitOfWork":
        """Start transaction scope."""
        self._session = self._session_factory()
        self._execution_id = ExecutionID.generate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit or rollback based on exception."""
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()

    @property
    def execution_id(self) -> ExecutionID:
        """Get current execution ID for tracing.

        Returns:
            ExecutionID value object
        """
        if self._execution_id is None:
            raise RuntimeError("UnitOfWork not initialized. Use async context manager.")
        return self._execution_id

    @property
    def orders(self) -> SqlAlchemyOrderRepository:
        """Lazy-load order repository.

        Returns:
            SqlAlchemyOrderRepository instance
        """
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use async context manager.")
        if self._order_repository is None:
            self._order_repository = SqlAlchemyOrderRepository(self._session)
        return self._order_repository

    async def commit(self) -> None:
        """Commit all pending changes."""
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use async context manager.")
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback all pending changes."""
        if self._session is None:
            raise RuntimeError("UnitOfWork not initialized. Use async context manager.")
        await self._session.rollback()


def create_uow(session_factory: async_sessionmaker) -> UnitOfWork:
    """Create a new Unit of Work instance.

    Args:
        session_factory: SQLAlchemy async session factory

    Returns:
        UnitOfWork instance
    """
    return UnitOfWork(session_factory)
