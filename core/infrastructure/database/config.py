import logging
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """
    Unified Database settings: loaded from .env (no prefix).
    Automatically builds DATABASE_URL.
    """

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "konozy"
    postgres_password: str = "201077"
    postgres_db: str = "konozy_ai"

    echo_sql: bool = False
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        case_sensitive = False

    @property
    def database_url(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = DatabaseSettings()


# ---------------------------------------------------------------------------------------

engine: Optional[AsyncEngine] = None


def create_engine() -> AsyncEngine:
    logger.info(f"Creating DB engine: {settings.database_url}")
    engine = create_async_engine(
        settings.database_url,
        echo=settings.echo_sql,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout,
        pool_recycle=settings.pool_recycle,
        pool_pre_ping=True,
    )
    return engine


def get_engine() -> AsyncEngine:
    global engine
    if engine is None:
        engine = create_engine()
    return engine


def get_session_factory():
    engine = get_engine()
    return sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
