"""Pytest configuration and fixtures for integration tests."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from core.data.models.base import Base
from core.application.services.order_service import OrderApplicationService


# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    """Create test session factory."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    yield session_factory


@pytest_asyncio.fixture
async def test_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def test_client(test_session_factory) -> TestClient:
    """Create FastAPI test client with test database session."""
    from apps.api.deps import get_order_service
    
    # Override dependency
    def override_get_order_service():
        return OrderApplicationService(session_factory=test_session_factory)
    
    app.dependency_overrides[get_order_service] = override_get_order_service
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()
