"""
Database configuration.

Manages database connection settings and engine creation.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
import logging


logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """
    Database configuration settings.
    
    Loaded from environment variables or .env file.
    """
    
    # Database URL
    database_url: str = "postgresql+asyncpg://konozy:konozy123@localhost:5432/konozy_db"
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # 1 hour
    
    # Echo SQL (for debugging)
    echo_sql: bool = False
    
    class Config:
        env_file = ".env"
        env_prefix = "DB_"
        extra = "ignore"  # Ignore extra fields from .env


# Global settings instance
settings = DatabaseSettings()


# =============================================================================
# ENGINE CREATION
# =============================================================================

def create_engine() -> AsyncEngine:
    """
    Create async SQLAlchemy engine.
    
    Returns:
        Configured async engine
    """
    logger.info(f"Creating database engine: {settings.database_url}")
    
    engine = create_async_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        pool_recycle=settings.pool_recycle,
        pool_pre_ping=True,  # Test connections before using
    )
    
    return engine


# Global engine instance
engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    """
    Get or create global engine instance.
    
    Returns:
        Global async engine
    """
    global engine
    
    if engine is None:
        engine = create_engine()
    
    return engine


# =============================================================================
# SESSION FACTORY
# =============================================================================

def get_session_factory():
    """
    Get session factory.
    
    Returns:
        Session factory for creating sessions
    """
    engine = get_engine()
    return sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_session() -> AsyncSession:
    """
    Get database session (generator).
    
    Yields:
        Async database session
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

async def init_database():
    """
    Initialize database.
    
    Creates all tables if they don't exist.
    """
    from core.infrastructure.database.models import Base
    
    logger.info("Initializing database...")
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("✅ Database initialized successfully")


async def close_database():
    """Close database connections."""
    global engine
    
    if engine:
        logger.info("Closing database connections...")
        await engine.dispose()
        engine = None
        logger.info("✅ Database connections closed")
