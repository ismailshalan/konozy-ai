"""Database Lifecycle Management - Async Version"""

from typing import Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.engine import make_url

_async_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_database() -> None:
    """Initialize async database engine and session factory."""
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        return

    from core.infrastructure.database.session import DATABASE_URL
    from core.infrastructure.database.models import Base

    # Parse and convert URL safely
    sync_url = make_url(DATABASE_URL)

    if not sync_url.drivername.startswith("postgresql"):
        raise ValueError(
            f"Expected PostgreSQL URL, got: {sync_url.drivername}"
        )

    async_url = sync_url.set(drivername="postgresql+asyncpg")

    _async_engine = create_async_engine(
        async_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )

    _async_session_factory = async_sessionmaker(
        bind=_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Create tables
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get async session factory."""
    if _async_session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _async_session_factory


async def close_database() -> None:
    """Close async database engine."""
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        await _async_engine.dispose()

    _async_engine = None
    _async_session_factory = None
