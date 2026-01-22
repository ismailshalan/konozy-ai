"""Integration tests for Orders API endpoints."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_create_order_success(test_client: TestClient):
    """Test POST /orders endpoint - successful order creation."""
    # Prepare test data
    order_data = {
        "order_id": "112-3456789-0123456",
        "purchase_date": "2025-01-13T10:30:00+00:00",
        "buyer_email": "buyer@example.com",
        "items": [
            {
                "sku": "SKU-001",
                "title": "Test Product 1",
                "quantity": 2,
                "unit_price_amount": "50.00",
                "unit_price_currency": "USD",
                "total_amount": "100.00",
                "total_currency": "USD",
            },
            {
                "sku": "SKU-002",
                "title": "Test Product 2",
                "quantity": 1,
                "unit_price_amount": "25.50",
                "unit_price_currency": "USD",
                "total_amount": "25.50",
                "total_currency": "USD",
            },
        ],
        "order_status": "Pending",
    }

    # Make POST request
    response = test_client.post("/api/v1/orders", json=order_data)

    # Verify HTTP response
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    
    response_data = response.json()
    
    # Verify response structure
    assert "order_id" in response_data
    assert response_data["order_id"] == order_data["order_id"]
    assert response_data["buyer_email"] == order_data["buyer_email"]
    assert len(response_data["items"]) == 2
    assert response_data["order_status"] == "Pending"
    
    # Verify ExecutionID is present and valid
    assert "execution_id" in response_data
    assert response_data["execution_id"] is not None
    assert isinstance(response_data["execution_id"], str)
    assert len(response_data["execution_id"]) > 0
    
    # Verify order total
    assert "order_total_amount" in response_data
    assert Decimal(response_data["order_total_amount"]) == Decimal("125.50")
    assert response_data["order_total_currency"] == "USD"
    
    # Verify data persistence by retrieving the order
    get_response = test_client.get(f"/api/v1/orders/{order_data['order_id']}")
    assert get_response.status_code == 200
    retrieved_data = get_response.json()
    assert retrieved_data["order_id"] == order_data["order_id"]
    assert retrieved_data["buyer_email"] == order_data["buyer_email"]
    assert len(retrieved_data["items"]) == 2
    assert Decimal(retrieved_data["order_total_amount"]) == Decimal("125.50")


@pytest.mark.asyncio
async def test_get_order_by_id(test_client: TestClient):
    """Test GET /orders/{order_id} endpoint."""
    # First create an order
    order_data = {
        "order_id": "112-9999999-9999999",
        "purchase_date": "2025-01-13T10:30:00+00:00",
        "buyer_email": "test@example.com",
        "items": [
            {
                "sku": "SKU-TEST",
                "title": "Test Product",
                "quantity": 1,
                "unit_price_amount": "10.00",
                "unit_price_currency": "USD",
                "total_amount": "10.00",
                "total_currency": "USD",
            }
        ],
        "order_status": "Pending",
    }
    
    create_response = test_client.post("/api/v1/orders", json=order_data)
    assert create_response.status_code == 201
    
    # Now retrieve it
    response = test_client.get(f"/api/v1/orders/{order_data['order_id']}")
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["order_id"] == order_data["order_id"]
    assert response_data["buyer_email"] == order_data["buyer_email"]
    assert "execution_id" in response_data


@pytest.mark.asyncio
async def test_get_order_not_found(test_client: TestClient):
    """Test GET /orders/{order_id} with non-existent order."""
    response = test_client.get("/api/v1/orders/112-NONEXISTENT-ORDER")
    
    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


@pytest.mark.asyncio
async def test_list_orders(test_client: TestClient):
    """Test GET /orders endpoint - list orders."""
    # Create multiple orders
    for i in range(3):
        order_data = {
            "order_id": f"112-1111111-{i:07d}",
            "purchase_date": "2025-01-13T10:30:00+00:00",
            "buyer_email": f"buyer{i}@example.com",
            "items": [
                {
                    "sku": f"SKU-{i}",
                    "title": f"Product {i}",
                    "quantity": 1,
                    "unit_price_amount": "10.00",
                    "unit_price_currency": "USD",
                    "total_amount": "10.00",
                    "total_currency": "USD",
                }
            ],
            "order_status": "Pending",
        }
        create_response = test_client.post("/api/v1/orders", json=order_data)
        assert create_response.status_code == 201
    
    # List orders
    response = test_client.get("/api/v1/orders?limit=10")
    
    assert response.status_code == 200
    orders = response.json()
    assert isinstance(orders, list)
    assert len(orders) >= 3  # At least the 3 we just created


@pytest.mark.asyncio
async def test_sync_orders(test_client: TestClient):
    """Test POST /api/v1/orders/sync endpoint."""
    # Make POST request to sync endpoint
    response = test_client.post("/api/v1/orders/sync", json={})
    
    # Verify HTTP response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    # Parse response
    body = response.json()
    
    # Verify response structure
    assert "execution_id" in body, "Response must contain execution_id"
    assert "status" in body, "Response must contain status"
    assert "message" in body, "Response must contain message"
    
    # Verify execution_id is valid
    assert body["execution_id"] is not None
    assert isinstance(body["execution_id"], str)
    assert len(body["execution_id"]) > 0
    
    # Verify status
    assert body["status"] == "started", f"Expected status 'started', got '{body['status']}'"
    
    # Verify message
    assert "started successfully" in body["message"].lower()
    
    # Verify marketplace (default should be "amazon")
    assert body.get("marketplace") == "amazon"
