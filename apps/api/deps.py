"""FastAPI dependencies for dependency injection."""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.application.services.order_service import OrderApplicationService
from core.data.uow import UnitOfWork, create_uow

# Database URL - should be moved to config in production
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/dbname"

# Create async engine
_engine = create_async_engine(DATABASE_URL, echo=False)

# Create session factory
_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get SQLAlchemy async session.

    Yields:
        AsyncSession instance
    """
    async with _session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get SQLAlchemy session factory.

    Returns:
        async_sessionmaker instance
    """
    return _session_factory


def get_uow() -> UnitOfWork:
    """Get Unit of Work instance.

    Returns:
        UnitOfWork instance
    """
    return create_uow(_session_factory)


def get_order_service() -> OrderApplicationService:
    """Get OrderApplicationService instance.

    Returns:
        OrderApplicationService instance
    """
    return OrderApplicationService(_session_factory)
