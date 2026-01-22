"""
Integration tests for Amazon SP-API integration.

Tests the complete SP-API integration:
- SP-API client authentication and signing
- Order fetching with items
- Domain mapping
- Event store integration
- Sync workflow
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from core.domain.value_objects import ExecutionID
from konozy_sdk.amazon import AmazonAPI
# map_amazon_order_to_domain is now inline in services - import Order and create inline
from core.domain.entities.order import Order, OrderItem
from core.domain.value_objects import OrderNumber, Money, ExecutionID
from datetime import datetime
from decimal import Decimal

def map_amazon_order_to_domain(raw_order: dict, execution_id: ExecutionID) -> Order:
    """Inline conversion function for tests."""
    amazon_order_id = raw_order.get("AmazonOrderId")
    if not amazon_order_id:
        raise ValueError("AmazonOrderId is required")
    
    purchase_date_str = raw_order.get("PurchaseDate")
    if not purchase_date_str:
        raise ValueError("PurchaseDate is required")
    
    try:
        purchase_date = datetime.fromisoformat(purchase_date_str.replace("Z", "+00:00"))
    except Exception:
        purchase_date = datetime.utcnow()
    
    buyer_email = raw_order.get("BuyerInfo", {}).get("BuyerEmail")
    order_status = raw_order.get("OrderStatus", "Pending")
    
    order_total = None
    if "OrderTotal" in raw_order:
        total_dict = raw_order["OrderTotal"]
        order_total = Money(
            amount=Decimal(str(total_dict.get("Amount", "0.00"))),
            currency=total_dict.get("CurrencyCode", "EGP")
        )
    
    items = []
    order_items = raw_order.get("OrderItems", [])
    for item_data in order_items:
        item_total = None
        if "ItemPrice" in item_data:
            price_dict = item_data["ItemPrice"]
            item_total = Money(
                amount=Decimal(str(price_dict.get("Amount", "0.00"))),
                currency=price_dict.get("CurrencyCode", "EGP")
            )
        
        items.append(OrderItem(
            sku=item_data.get("SellerSKU", ""),
            title=item_data.get("Title"),
            quantity=int(item_data.get("QuantityOrdered", 1)),
            unit_price=Money(
                amount=Decimal(str(item_data.get("ItemPrice", {}).get("Amount", "0.00"))),
                currency=item_data.get("ItemPrice", {}).get("CurrencyCode", "EGP")
            ) if "ItemPrice" in item_data else Money(amount=Decimal("0.00"), currency="EGP"),
            total=item_total or Money(amount=Decimal("0.00"), currency="EGP"),
        ))
    
    return Order(
        order_id=OrderNumber(value=amazon_order_id),
        purchase_date=purchase_date,
        buyer_email=buyer_email or "",
        items=items,
        order_total=order_total,
        order_status=order_status,
        execution_id=execution_id,
        marketplace="amazon",
    )
# Note: AmazonSPAPIClient and AmazonOrderClient replaced with AmazonAPI from SDK
from core.settings.modules.amazon_settings import AmazonSettings


# Mock SP-API responses
MOCK_SPAPI_ORDERS_RESPONSE = {
    "payload": {
        "Orders": [
            {
                "AmazonOrderId": "112-3456789-0123456",
                "PurchaseDate": "2025-01-13T10:30:00+00:00",
                "OrderStatus": "Shipped",
                "BuyerInfo": {
                    "BuyerEmail": "buyer1@example.com"
                },
                "OrderTotal": {
                    "Amount": "125.50",
                    "CurrencyCode": "USD"
                },
            },
            {
                "AmazonOrderId": "112-9999999-9999999",
                "PurchaseDate": "2025-01-14T10:30:00+00:00",
                "OrderStatus": "Pending",
                "BuyerInfo": {
                    "BuyerEmail": "buyer2@example.com"
                },
                "OrderTotal": {
                    "Amount": "50.00",
                    "CurrencyCode": "USD"
                },
            },
        ]
    }
}

MOCK_SPAPI_ORDER_ITEMS_RESPONSE_1 = {
    "payload": {
        "OrderItems": [
            {
                "ASIN": "B01234567",
                "SellerSKU": "SKU-001",
                "Title": "Test Product 1",
                "QuantityOrdered": 2,
                "ItemPrice": {
                    "Amount": "50.00",
                    "CurrencyCode": "USD"
                },
            },
            {
                "ASIN": "B09876543",
                "SellerSKU": "SKU-002",
                "Title": "Test Product 2",
                "QuantityOrdered": 1,
                "ItemPrice": {
                    "Amount": "25.50",
                    "CurrencyCode": "USD"
                },
            },
        ]
    }
}

MOCK_SPAPI_ORDER_ITEMS_RESPONSE_2 = {
    "payload": {
        "OrderItems": [
            {
                "ASIN": "B01111111",
                "SellerSKU": "SKU-003",
                "Title": "Test Product 3",
                "QuantityOrdered": 1,
                "ItemPrice": {
                    "Amount": "50.00",
                    "CurrencyCode": "USD"
                },
            },
        ]
    }
}


@pytest.fixture
def mock_amazon_settings():
    """Create mock Amazon settings."""
    return AmazonSettings(
        seller_id="TEST_SELLER",
        refresh_token="test_refresh_token",
        lwa_app_id="test_lwa_app_id",
        lwa_client_secret="test_lwa_client_secret",
        amazon_access_key="test_access_key",
        amazon_secret_key="test_secret_key",
        role_arn="arn:aws:iam::123456789012:role/test",
        role_session_name="konozy-session",
        marketplace="EG",
        account_id=1,
        sales_id=1,
        amazon_partner_id=1,
        commissions_id=1,
        fees_product_id=1,
        promo_rebates_id=1,
        inventory_loss_id=1,
        fba_pick_pack_fee_id=1,
        cod_fee_id=1,
        fba_fee_account_id=1,
        journal_id=1,
        analytic_sales_id=1,
        analytic_shipping_cost_id=1,
        analytic_commissions_id=1,
    )


@pytest.mark.asyncio
async def test_spapi_client_list_orders(mock_amazon_settings):
    """Test SP-API client list_orders method."""
    
    with patch('core.infrastructure.marketplace.amazon.spapi_client.aiohttp.ClientSession') as mock_session:
        # Mock LWA token response
        mock_token_response = AsyncMock()
        mock_token_response.status = 200
        mock_token_response.json = AsyncMock(return_value={
            "access_token": "test_access_token",
            "expires_in": 3600
        })
        
        # Mock SP-API orders response
        mock_orders_response = AsyncMock()
        mock_orders_response.status = 200
        mock_orders_response.headers = {}
        mock_orders_response.json = AsyncMock(return_value=MOCK_SPAPI_ORDERS_RESPONSE)
        
        # Setup session mock
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        mock_session_instance.post.return_value.__aenter__.return_value = mock_token_response
        mock_session_instance.request.return_value.__aenter__.return_value = mock_orders_response
        
        client = AmazonSPAPIClient(mock_amazon_settings)
        orders = await client.list_orders(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )
        
        assert len(orders) == 2
        assert orders[0]["AmazonOrderId"] == "112-3456789-0123456"
        assert orders[1]["AmazonOrderId"] == "112-9999999-9999999"


@pytest.mark.asyncio
async def test_spapi_client_list_order_items(mock_amazon_settings):
    """Test SP-API client list_order_items method."""
    
    with patch('core.infrastructure.marketplace.amazon.spapi_client.aiohttp.ClientSession') as mock_session:
        # Mock LWA token response
        mock_token_response = AsyncMock()
        mock_token_response.status = 200
        mock_token_response.json = AsyncMock(return_value={
            "access_token": "test_access_token",
            "expires_in": 3600
        })
        
        # Mock SP-API items response
        mock_items_response = AsyncMock()
        mock_items_response.status = 200
        mock_items_response.headers = {}
        mock_items_response.json = AsyncMock(return_value=MOCK_SPAPI_ORDER_ITEMS_RESPONSE_1)
        
        # Setup session mock
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        mock_session_instance.post.return_value.__aenter__.return_value = mock_token_response
        mock_session_instance.request.return_value.__aenter__.return_value = mock_items_response
        
        client = AmazonSPAPIClient(mock_amazon_settings)
        items = await client.list_order_items("112-3456789-0123456")
        
        assert len(items) == 2
        assert items[0]["SellerSKU"] == "SKU-001"
        assert items[1]["SellerSKU"] == "SKU-002"


@pytest.mark.asyncio
async def test_amazon_order_client_fetch_orders_with_items(mock_amazon_settings):
    """Test AmazonOrderClient fetches orders and merges items."""
    
    with patch('core.infrastructure.marketplace.amazon.spapi_client.aiohttp.ClientSession') as mock_session:
        # Mock LWA token response
        mock_token_response = AsyncMock()
        mock_token_response.status = 200
        mock_token_response.json = AsyncMock(return_value={
            "access_token": "test_access_token",
            "expires_in": 3600
        })
        
        # Mock SP-API responses
        mock_orders_response = AsyncMock()
        mock_orders_response.status = 200
        mock_orders_response.headers = {}
        mock_orders_response.json = AsyncMock(return_value=MOCK_SPAPI_ORDERS_RESPONSE)
        
        mock_items_response_1 = AsyncMock()
        mock_items_response_1.status = 200
        mock_items_response_1.headers = {}
        mock_items_response_1.json = AsyncMock(return_value=MOCK_SPAPI_ORDER_ITEMS_RESPONSE_1)
        
        mock_items_response_2 = AsyncMock()
        mock_items_response_2.status = 200
        mock_items_response_2.headers = {}
        mock_items_response_2.json = AsyncMock(return_value=MOCK_SPAPI_ORDER_ITEMS_RESPONSE_2)
        
        # Setup session mock
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        mock_session_instance.post.return_value.__aenter__.return_value = mock_token_response
        
        # First request is list_orders, then two list_order_items calls
        mock_session_instance.request.return_value.__aenter__.side_effect = [
            mock_orders_response,
            mock_items_response_1,
            mock_items_response_2,
        ]
        
        spapi_client = AmazonSPAPIClient(mock_amazon_settings)
        order_client = AmazonOrderClient(spapi_client)
        
        orders = await order_client.fetch_orders(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )
        
        # Verify orders are returned
        assert len(orders) == 2
        
        # Verify first order has items merged
        assert "Items" in orders[0]
        assert "OrderItems" in orders[0]
        assert len(orders[0]["Items"]) == 2
        assert orders[0]["Items"][0]["SellerSKU"] == "SKU-001"
        
        # Verify second order has items merged
        assert "Items" in orders[1]
        assert len(orders[1]["Items"]) == 1
        assert orders[1]["Items"][0]["SellerSKU"] == "SKU-003"


@pytest.mark.asyncio
async def test_mapper_handles_spapi_format(mock_amazon_settings):
    """Test mapper correctly handles SP-API response format."""
    
    # Create order data in SP-API format
    spapi_order = {
        "AmazonOrderId": "112-3456789-0123456",
        "PurchaseDate": "2025-01-13T10:30:00+00:00",
        "OrderStatus": "Shipped",
        "BuyerInfo": {
            "BuyerEmail": "buyer@example.com"
        },
        "OrderTotal": {
            "Amount": "125.50",
            "CurrencyCode": "USD"
        },
        "Items": [
            {
                "ASIN": "B01234567",
                "SellerSKU": "SKU-001",
                "Title": "Test Product 1",
                "QuantityOrdered": 2,
                "ItemPrice": {
                    "Amount": "50.00",
                    "CurrencyCode": "USD"
                },
            },
        ]
    }
    
    execution_id = ExecutionID.generate()
    order = map_amazon_order_to_domain(spapi_order, execution_id)
    
    # Verify order mapping
    assert order.order_id.value == "112-3456789-0123456"
    assert order.buyer_email == "buyer@example.com"
    assert order.order_status == "Shipped"
    assert len(order.items) == 1
    
    # Verify order total
    assert order.order_total is not None
    assert order.order_total.amount == Decimal("125.50")
    assert order.order_total.currency == "USD"
    
    # Verify item mapping
    item = order.items[0]
    assert item.sku == "SKU-001"
    assert item.title == "Test Product 1"
    assert item.quantity == 2
    assert item.unit_price.amount == Decimal("50.00")


@pytest.mark.asyncio
async def test_sync_orders_with_spapi_integration(test_client):
    """Test sync_orders endpoint with SP-API integration."""
    from fastapi.testclient import TestClient
    
    # Mock SP-API client responses
    with patch('api.dependencies.get_spapi_client') as mock_get_spapi:
        mock_spapi = MagicMock()
        mock_spapi.list_orders = AsyncMock(return_value=MOCK_SPAPI_ORDERS_RESPONSE["payload"]["Orders"])
        mock_spapi.list_order_items = AsyncMock(side_effect=[
            MOCK_SPAPI_ORDER_ITEMS_RESPONSE_1["payload"]["OrderItems"],
            MOCK_SPAPI_ORDER_ITEMS_RESPONSE_2["payload"]["OrderItems"],
        ])
        mock_get_spapi.return_value = mock_spapi
        
        # Mock LWA token
        with patch('core.infrastructure.marketplace.amazon.spapi_client.aiohttp.ClientSession') as mock_session:
            mock_token_response = AsyncMock()
            mock_token_response.status = 200
            mock_token_response.json = AsyncMock(return_value={
                "access_token": "test_token",
                "expires_in": 3600
            })
            
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.post.return_value.__aenter__.return_value = mock_token_response
            
            # Mock sync service
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
                
                # Make request
                response = test_client.post("/api/v1/orders/sync", json={})
                
                assert response.status_code == 200
                body = response.json()
                
                # Verify response
                assert body["status"] == "completed"
                assert "execution_id" in body
                assert body["total_orders"] == 2
                assert body["created_invoices"] == 2
                assert body["successful"] == 2


@pytest.mark.asyncio
async def test_spapi_throttling_handling(mock_amazon_settings):
    """Test SP-API client handles throttling (429) correctly."""
    
    with patch('core.infrastructure.marketplace.amazon.spapi_client.aiohttp.ClientSession') as mock_session:
        # Mock LWA token response
        mock_token_response = AsyncMock()
        mock_token_response.status = 200
        mock_token_response.json = AsyncMock(return_value={
            "access_token": "test_access_token",
            "expires_in": 3600
        })
        
        # Mock throttling response (429) then success
        mock_throttle_response = AsyncMock()
        mock_throttle_response.status = 429
        mock_throttle_response.headers = {"Retry-After": "1"}
        mock_throttle_response.text = AsyncMock(return_value="Rate limited")
        
        mock_success_response = AsyncMock()
        mock_success_response.status = 200
        mock_success_response.headers = {}
        mock_success_response.json = AsyncMock(return_value=MOCK_SPAPI_ORDERS_RESPONSE)
        
        # Setup session mock
        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        mock_session_instance.post.return_value.__aenter__.return_value = mock_token_response
        mock_session_instance.request.return_value.__aenter__.side_effect = [
            mock_throttle_response,
            mock_success_response,
        ]
        
        client = AmazonSPAPIClient(mock_amazon_settings)
        
        # Should retry after throttling
        orders = await client.list_orders()
        
        assert len(orders) == 2
        # Verify retry was attempted
        assert mock_session_instance.request.call_count == 2
