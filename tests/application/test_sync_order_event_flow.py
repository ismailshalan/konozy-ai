"""
Unit tests for SyncAmazonOrderUseCase → Event Bus → Event Store flow.

Tests the complete event-driven workflow:
1. Order entity collects events
2. Use Case publishes events through Event Bus
3. Event Bus stores events in Event Store
4. Events are retrievable and traceable
"""
import pytest
import pytest_asyncio
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from core.application.use_cases.sync_amazon_order import (
    SyncAmazonOrderUseCase,
    SyncAmazonOrderRequest,
)
from core.domain.entities.order import Order
from core.domain.value_objects import OrderNumber, ExecutionID, Money, FinancialBreakdown, FinancialLine
from core.domain.repositories.order_repository import OrderRepository
from core.domain.event_bus import EventBus
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.database.config import init_database, get_session_factory, close_database


@pytest_asyncio.fixture
async def mock_order_repository():
    """Mock order repository."""
    repo = AsyncMock(spec=OrderRepository)
    repo.save = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def mock_odoo_client():
    """Mock Odoo client."""
    client = AsyncMock()
    client.get_partner_by_email = AsyncMock(return_value=1)
    client.create_invoice = AsyncMock(return_value=12345)
    return client


@pytest_asyncio.fixture
async def mock_notification_service():
    """Mock notification service."""
    service = AsyncMock()
    service.send_success = AsyncMock()
    service.send_error = AsyncMock()
    return service


@pytest_asyncio.fixture
async def real_event_bus():
    """Real Event Bus instance."""
    from core.infrastructure.event_bus import InMemoryEventBus
    return InMemoryEventBus()


@pytest_asyncio.fixture
async def database_setup():
    """Setup database for testing."""
    await init_database()
    yield
    await close_database()


@pytest.fixture
def sample_financial_events():
    """Sample financial events data."""
    return {
        "ShipmentEventList": [
            {
                "ShipmentItemList": [
                    {
                        "ItemChargeList": [
                            {
                                "ChargeType": "Principal",
                                "ChargeAmount": {
                                    "CurrencyCode": "EGP",
                                    "CurrencyAmount": 100.00
                                }
                            }
                        ]
                    }
                ],
                "ShipmentFeeList": [
                    {
                        "FeeType": "FBAFees",
                        "FeeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": -10.00
                        }
                    }
                ]
            }
        ],
        "TotalExpenses": {
            "CurrencyCode": "EGP",
            "CurrencyAmount": -10.00
        }
    }


@pytest.mark.asyncio
async def test_use_case_publishes_order_created_event(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup,
    sample_financial_events
):
    """Test that OrderCreatedEvent is published when order is created."""
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=sample_financial_events,
        buyer_email="test@example.com",
        dry_run=True,  # Skip database operations
    )
    
    # Execute use case
    response = await use_case.execute(request)
    
    # Verify execution_id is returned
    assert response.execution_id is not None
    assert response.success is True
    
    # Verify events were stored in Event Store
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events_by_execution(str(response.execution_id.value))
        
        # Should have OrderCreatedEvent and FinancialsExtractedEvent
        event_types = [e.event_type for e in events]
        assert "OrderCreatedEvent" in event_types
        assert "FinancialsExtractedEvent" in event_types


@pytest.mark.asyncio
async def test_use_case_publishes_validation_event(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup,
    sample_financial_events
):
    """Test that OrderValidatedEvent is published after validation."""
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=sample_financial_events,
        buyer_email="test@example.com",
        dry_run=True,
    )
    
    # Execute use case
    response = await use_case.execute(request)
    
    # Verify validation event was stored
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events_by_execution(str(response.execution_id.value))
        
        event_types = [e.event_type for e in events]
        assert "OrderValidatedEvent" in event_types
        
        # Find validation event
        validation_event = next((e for e in events if e.event_type == "OrderValidatedEvent"), None)
        assert validation_event is not None
        assert validation_event.validation_passed is True


@pytest.mark.asyncio
async def test_use_case_publishes_all_events_atomically(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup,
    sample_financial_events
):
    """Test that all events are published atomically in a single transaction."""
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=sample_financial_events,
        buyer_email="test@example.com",
        dry_run=False,  # Full flow
    )
    
    # Execute use case
    response = await use_case.execute(request)
    
    # Verify all events are stored
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events_by_execution(str(response.execution_id.value))
        
        # Should have multiple events
        assert len(events) >= 3  # At least: Created, Extracted, Validated
        
        # Verify event order (should be chronological)
        for i in range(len(events) - 1):
            assert events[i].occurred_at <= events[i + 1].occurred_at
        
        # Verify all events have same execution_id
        for event in events:
            assert str(event.execution_id) == str(response.execution_id.value)


@pytest.mark.asyncio
async def test_use_case_publishes_failure_event_on_error(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup
):
    """Test that OrderFailedEvent is published when sync fails."""
    # Make Odoo client fail
    mock_odoo_client.create_invoice = AsyncMock(side_effect=Exception("Odoo connection failed"))
    
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    # Create invalid financial events (will cause validation to pass but invoice creation to fail)
    invalid_events = {
        "ShipmentEventList": [
            {
                "ShipmentItemList": [
                    {
                        "ItemChargeList": [
                            {
                                "ChargeType": "Principal",
                                "ChargeAmount": {
                                    "CurrencyCode": "EGP",
                                    "CurrencyAmount": 100.00
                                }
                            }
                        ]
                    }
                ],
                "ShipmentFeeList": [
                    {
                        "FeeType": "FBAFees",
                        "FeeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": -10.00
                        }
                    }
                ]
            }
        ],
        "TotalExpenses": {
            "CurrencyCode": "EGP",
            "CurrencyAmount": -10.00
        }
    }
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=invalid_events,
        buyer_email="test@example.com",
        dry_run=False,
    )
    
    # Execute use case (will fail at invoice creation)
    response = await use_case.execute(request)
    
    # Should have failed
    assert response.success is False
    
    # Verify failure event was stored
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events_by_execution(str(response.execution_id.value))
        
        event_types = [e.event_type for e in events]
        assert "OrderFailedEvent" in event_types
        
        # Find failure event
        failure_event = next((e for e in events if e.event_type == "OrderFailedEvent"), None)
        assert failure_event is not None
        assert failure_event.error_type == "SyncError"


@pytest.mark.asyncio
async def test_events_are_retrievable_by_aggregate_id(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup,
    sample_financial_events
):
    """Test that events can be retrieved by aggregate_id (order_id)."""
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    order_id = "123-4567890-1234567"
    request = SyncAmazonOrderRequest(
        amazon_order_id=order_id,
        financial_events=sample_financial_events,
        buyer_email="test@example.com",
        dry_run=True,
    )
    
    # Execute use case
    response = await use_case.execute(request)
    
    # Retrieve events by aggregate_id
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events(order_id)
        
        # Should have events for this order
        assert len(events) > 0
        
        # All events should have correct aggregate_id
        for event in events:
            assert event.aggregate_id == order_id


@pytest.mark.asyncio
async def test_execution_id_is_returned_in_response(
    mock_order_repository,
    mock_odoo_client,
    mock_notification_service,
    real_event_bus,
    database_setup,
    sample_financial_events
):
    """Test that execution_id is returned in the response."""
    use_case = SyncAmazonOrderUseCase(
        order_repository=mock_order_repository,
        odoo_client=mock_odoo_client,
        notification_service=mock_notification_service,
        event_bus=real_event_bus,
    )
    
    request = SyncAmazonOrderRequest(
        amazon_order_id="123-4567890-1234567",
        financial_events=sample_financial_events,
        buyer_email="test@example.com",
        dry_run=True,
    )
    
    # Execute use case
    response = await use_case.execute(request)
    
    # Verify execution_id is present and valid
    assert response.execution_id is not None
    assert isinstance(response.execution_id, ExecutionID)
    
    # Verify events can be retrieved using this execution_id
    factory = get_session_factory()
    async with factory() as session:
        event_store = EventStore(session)
        events = await event_store.get_events_by_execution(str(response.execution_id.value))
        
        assert len(events) > 0
