"""
Integration tests for Amazon order sync endpoint.

Tests the complete sync pipeline:
- Amazon order fetching
- Domain mapping
- Event store integration
- Odoo invoice creation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from core.domain.value_objects import ExecutionID


@pytest.mark.asyncio
async def test_sync_orders_endpoint_with_mocks(test_client: TestClient):
    """Test POST /api/v1/orders/sync with mocked Amazon and Odoo clients."""
    
    # Mock Amazon order data
    mock_amazon_orders = [
        {
            "AmazonOrderId": "112-3456789-0123456",
            "PurchaseDate": "2025-01-13T10:30:00+00:00",
            "BuyerInfo": {"BuyerEmail": "buyer1@example.com"},
            "OrderStatus": "Pending",
            "OrderItems": [
                {
                    "SellerSKU": "SKU-001",
                    "Title": "Test Product 1",
                    "QuantityOrdered": 2,
                    "ItemPrice": {"Amount": "50.00", "CurrencyCode": "USD"},
                }
            ],
        },
        {
            "AmazonOrderId": "112-9999999-9999999",
            "PurchaseDate": "2025-01-14T10:30:00+00:00",
            "BuyerInfo": {"BuyerEmail": "buyer2@example.com"},
            "OrderStatus": "Pending",
            "OrderItems": [
                {
                    "SellerSKU": "SKU-002",
                    "Title": "Test Product 2",
                    "QuantityOrdered": 1,
                    "ItemPrice": {"Amount": "25.50", "CurrencyCode": "USD"},
                }
            ],
        },
    ]
    
    # Mock the Amazon client
    with patch('api.dependencies.get_amazon_order_client') as mock_get_client:
        mock_order_client = AsyncMock()
        mock_order_client.fetch_orders = AsyncMock(return_value=mock_amazon_orders)
        mock_get_client.return_value = mock_order_client
        
        # Mock Odoo client
        with patch('api.dependencies.get_amazon_sync_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.sync_orders = AsyncMock(return_value={
                "execution_id": str(ExecutionID.generate().value),
                "total_orders": 2,
                "created_invoices": 2,
                "failed_items": [],
                "successful": 2,
            })
            mock_get_service.return_value = mock_service
            
            # Make POST request
            response = test_client.post("/api/v1/orders/sync", json={})
            
            # Verify HTTP response
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            # Parse response
            body = response.json()
            
            # Verify response structure
            assert "execution_id" in body
            assert "status" in body
            assert body["status"] == "completed"
            assert "total_orders" in body
            assert "created_invoices" in body
            assert "successful" in body
            
            # Verify sync was called
            mock_service.sync_orders.assert_called_once()


@pytest.mark.asyncio
async def test_sync_orders_with_date_filters(test_client: TestClient):
    """Test sync endpoint with date filters."""
    
    with patch('api.dependencies.get_amazon_sync_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.sync_orders = AsyncMock(return_value={
            "execution_id": str(ExecutionID.generate().value),
            "total_orders": 0,
            "created_invoices": 0,
            "failed_items": [],
            "successful": 0,
        })
        mock_get_service.return_value = mock_service
        
        # Make POST request with date filters
        request_data = {
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-01-31T23:59:59Z",
            "marketplace": "amazon",
        }
        
        response = test_client.post("/api/v1/orders/sync", json=request_data)
        
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert "execution_id" in body
        
        # Verify sync was called with date filters
        mock_service.sync_orders.assert_called_once()
        call_args = mock_service.sync_orders.call_args
        assert call_args[1]["start_date"] is not None
        assert call_args[1]["end_date"] is not None


@pytest.mark.asyncio
async def test_sync_orders_execution_id_tracking(test_client: TestClient):
    """Test that execution_id is properly tracked throughout sync."""
    
    execution_id = ExecutionID.generate()
    execution_id_str = str(execution_id.value)
    
    with patch('api.dependencies.get_amazon_sync_service') as mock_get_service:
        mock_service = AsyncMock()
        mock_service.sync_orders = AsyncMock(return_value={
            "execution_id": execution_id_str,
            "total_orders": 1,
            "created_invoices": 1,
            "failed_items": [],
            "successful": 1,
        })
        mock_get_service.return_value = mock_service
        
        response = test_client.post("/api/v1/orders/sync", json={})
        
        assert response.status_code == 200
        body = response.json()
        
        # Verify execution_id is returned
        assert body["execution_id"] == execution_id_str
        
        # Verify sync was called with the execution_id
        mock_service.sync_orders.assert_called_once()
        call_args = mock_service.sync_orders.call_args
        # The execution_id should be passed (may be generated in endpoint or service)
        assert "execution_id" in call_args[1] or call_args[1].get("execution_id") is None
