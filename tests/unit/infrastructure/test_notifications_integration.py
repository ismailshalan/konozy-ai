"""
Unit tests for notification service integration with sync service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.domain.value_objects import ExecutionID
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService
from core.application.services.amazon_sync_service import AmazonSyncService
from core.application.use_cases.sync_amazon_order import SyncAmazonOrderUseCase


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service for testing."""
    return MockNotificationService()


@pytest.fixture
def mock_sync_order_use_case():
    """Create a mock sync order use case."""
    return MagicMock(spec=SyncAmazonOrderUseCase)


@pytest.fixture
def mock_amazon_order_client():
    """Create a mock Amazon order client."""
    client = MagicMock()
    client.fetch_orders = AsyncMock(return_value=[])
    return client


@pytest.fixture
def amazon_sync_service_with_notifications(
    mock_sync_order_use_case,
    mock_amazon_order_client,
    mock_notification_service,
):
    """Create AmazonSyncService with notification service."""
    return AmazonSyncService(
        sync_order_use_case=mock_sync_order_use_case,
        amazon_order_client=mock_amazon_order_client,
        notification_service=mock_notification_service,
    )


@pytest.mark.asyncio
async def test_sync_orders_calls_notify_on_completion(
    amazon_sync_service_with_notifications,
    mock_notification_service,
):
    """Test that sync_orders() calls notify() when sync completes."""
    # Execute sync
    result = await amazon_sync_service_with_notifications.sync_orders()
    
    # Check that notification was sent
    notifications = mock_notification_service.get_notifications()
    
    # Should have at least one notification
    assert len(notifications) > 0
    
    # Check for generic notification with severity 80
    generic_notifications = [
        n for n in notifications
        if n.get("type") == "generic" and n.get("severity") == 80
    ]
    
    assert len(generic_notifications) > 0
    
    # Check notification message contains expected info
    notification = generic_notifications[0]
    message = notification["message"]
    assert "Amazon sync completed" in message
    assert "exec=" in message
    assert "orders=" in message


@pytest.mark.asyncio
async def test_sync_orders_notification_message_format(
    amazon_sync_service_with_notifications,
    mock_notification_service,
):
    """Test that notification message has correct format."""
    result = await amazon_sync_service_with_notifications.sync_orders()
    
    notifications = mock_notification_service.get_notifications()
    generic_notifications = [
        n for n in notifications
        if n.get("type") == "generic"
    ]
    
    assert len(generic_notifications) > 0
    
    message = generic_notifications[0]["message"]
    
    # Check message format
    assert "[KONOZY]" in message
    assert "exec=" in message
    assert "orders=" in message
    assert "invoices_ok=" in message
    assert "invoices_failed=" in message


@pytest.mark.asyncio
async def test_sync_orders_notification_severity(
    amazon_sync_service_with_notifications,
    mock_notification_service,
):
    """Test that notification is sent with correct severity (80)."""
    await amazon_sync_service_with_notifications.sync_orders()
    
    notifications = mock_notification_service.get_notifications()
    generic_notifications = [
        n for n in notifications
        if n.get("type") == "generic"
    ]
    
    assert len(generic_notifications) > 0
    
    # Check severity is 80
    notification = generic_notifications[0]
    assert notification["severity"] == 80


@pytest.mark.asyncio
async def test_sync_orders_no_notification_if_service_not_provided(
    mock_sync_order_use_case,
    mock_amazon_order_client,
):
    """Test that sync works even without notification service."""
    service = AmazonSyncService(
        sync_order_use_case=mock_sync_order_use_case,
        amazon_order_client=mock_amazon_order_client,
        notification_service=None,  # No notification service
    )
    
    # Should not raise error
    result = await service.sync_orders()
    
    assert result is not None
    assert "execution_id" in result


@pytest.mark.asyncio
async def test_notification_service_notify_method_exists(mock_notification_service):
    """Test that notification service has notify() method."""
    assert hasattr(mock_notification_service, 'notify')
    assert callable(getattr(mock_notification_service, 'notify'))


@pytest.mark.asyncio
async def test_notification_service_notify_called_with_correct_params(
    mock_notification_service,
):
    """Test that notify() can be called with message and severity."""
    message = "[KONOZY] Test notification"
    severity = 80
    
    # Should not raise
    await mock_notification_service.notify(message, severity)
    
    # Check notification was recorded
    notifications = mock_notification_service.get_notifications()
    assert len(notifications) > 0
    
    # Find the notification
    notification = next(
        (n for n in notifications if n.get("type") == "generic"),
        None
    )
    
    assert notification is not None
    assert notification["message"] == message
    assert notification["severity"] == severity
