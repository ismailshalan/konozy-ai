"""FastAPI dependencies for dependency injection."""

from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.application.services.order_service import OrderApplicationService
from core.application.services.amazon_sync_service import AmazonSyncService
from core.application.use_cases.sync_amazon_order import SyncAmazonOrderUseCase
from core.data.uow import UnitOfWork, create_uow

# Mock implementations for Amazon sync (can be replaced with real ones)
from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
from core.infrastructure.adapters.odoo.mock_odoo_client import MockOdooClient
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService

# Database URL - Using SQLite for development (easier setup, no auth required)
# For production, switch to PostgreSQL: "postgresql+asyncpg://user:password@localhost/dbname"
DB_PATH = Path("konozy.db").absolute()
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Create async engine with SQLite-specific configuration
_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # Required for SQLite
    poolclass=StaticPool,  # SQLite doesn't support connection pooling well
)

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


# =============================================================================
# AMAZON SYNC DEPENDENCIES (singleton instances)
# =============================================================================

_amazon_order_repository = None
_amazon_odoo_client = None
_amazon_notification_service = None
_amazon_sync_use_case = None
_amazon_sync_service = None


def get_amazon_sync_service() -> AmazonSyncService:
    """Get AmazonSyncService instance.

    Returns:
        AmazonSyncService instance
    """
    global _amazon_order_repository, _amazon_odoo_client, _amazon_notification_service
    global _amazon_sync_use_case, _amazon_sync_service
    
    if _amazon_sync_service is None:
        # Create mock dependencies for now
        if _amazon_order_repository is None:
            _amazon_order_repository = MockOrderRepository()
        if _amazon_odoo_client is None:
            _amazon_odoo_client = MockOdooClient()
        if _amazon_notification_service is None:
            _amazon_notification_service = MockNotificationService()
        
        # Create use case
        if _amazon_sync_use_case is None:
            from core.infrastructure.event_bus import get_event_bus
            _amazon_sync_use_case = SyncAmazonOrderUseCase(
                order_repository=_amazon_order_repository,
                odoo_client=_amazon_odoo_client,
                notification_service=_amazon_notification_service,
                event_bus=get_event_bus()
            )
        
        # Create service
        _amazon_sync_service = AmazonSyncService(
            sync_order_use_case=_amazon_sync_use_case
        )
    
    return _amazon_sync_service
