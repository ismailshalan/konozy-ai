"""
Integration tests for execution monitoring endpoints.
"""
import pytest
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from core.domain.value_objects import ExecutionID
from core.domain.events.order_events import (
    SyncStartedEvent,
    SyncCompletedEvent,
    OrderFetchedEvent,
    InvoiceCreatedEvent,
    InvoiceFailedEvent,
)
from core.infrastructure.database.event_store import EventStore
from core.infrastructure.database.lifecycle import get_session_factory
from core.data.uow import create_uow


@pytest.fixture
def test_execution_id():
    """Generate a test execution ID."""
    return str(ExecutionID.generate().value)


@pytest.fixture
async def test_events_in_store(test_execution_id):
    """Create test events in the event store."""
    session_factory = get_session_factory()
    uow = create_uow(session_factory)
    
    async with uow:
        event_store = EventStore(uow._session)
        
        # Create SyncStartedEvent
        sync_started = SyncStartedEvent(
            aggregate_id=f"sync-{test_execution_id}",
            execution_id=test_execution_id,
            marketplace="amazon",
            start_date="2025-01-01T00:00:00Z",
            end_date="2025-01-31T23:59:59Z",
        )
        await event_store.append(sync_started)
        
        # Create OrderFetchedEvent
        order_fetched = OrderFetchedEvent(
            aggregate_id="112-3456789-0123456",
            execution_id=test_execution_id,
            order_id="112-3456789-0123456",
            marketplace="amazon",
            buyer_email="test@example.com",
            purchase_date="2025-01-15T10:30:00Z",
        )
        await event_store.append(order_fetched)
        
        # Create InvoiceCreatedEvent
        invoice_created = InvoiceCreatedEvent(
            aggregate_id="112-3456789-0123456",
            execution_id=test_execution_id,
            order_id="112-3456789-0123456",
            invoice_id=12345,
            partner_id=67890,
            invoice_lines_count=2,
        )
        await event_store.append(invoice_created)
        
        # Create SyncCompletedEvent
        sync_completed = SyncCompletedEvent(
            aggregate_id=f"sync-{test_execution_id}",
            execution_id=test_execution_id,
            marketplace="amazon",
            total_orders=1,
            successful=1,
            failed=0,
            invoices_created=1,
            invoices_failed=0,
        )
        await event_store.append(sync_completed)
        
        await uow.commit()
    
    return test_execution_id


@pytest.mark.asyncio
async def test_get_execution_summary(test_client: TestClient, test_events_in_store):
    """Test GET /api/v1/executions/{execution_id} endpoint."""
    execution_id = test_events_in_store
    
    response = test_client.get(f"/api/v1/executions/{execution_id}")
    
    assert response.status_code == 200
    body = response.json()
    
    assert body["execution_id"] == execution_id
    assert body["status"] in ["completed", "completed_with_errors"]
    assert body["marketplace"] == "amazon"
    assert body["total_orders"] == 1
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["invoices_created"] == 1
    assert body["invoices_failed"] == 0
    assert body["started_at"] is not None
    assert body["completed_at"] is not None


@pytest.mark.asyncio
async def test_get_execution_summary_not_found(test_client: TestClient):
    """Test GET /api/v1/executions/{execution_id} with non-existent ID."""
    fake_id = str(uuid4())
    
    response = test_client.get(f"/api/v1/executions/{fake_id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_execution_summary_invalid_format(test_client: TestClient):
    """Test GET /api/v1/executions/{execution_id} with invalid format."""
    invalid_id = "not-a-uuid"
    
    response = test_client.get(f"/api/v1/executions/{invalid_id}")
    
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_execution_events(test_client: TestClient, test_events_in_store):
    """Test GET /api/v1/executions/{execution_id}/events endpoint."""
    execution_id = test_events_in_store
    
    response = test_client.get(f"/api/v1/executions/{execution_id}/events")
    
    assert response.status_code == 200
    events = response.json()
    
    assert isinstance(events, list)
    assert len(events) >= 4  # At least sync_started, order_fetched, invoice_created, sync_completed
    
    # Check event types
    event_types = [e["event_type"] for e in events]
    assert "sync_started" in event_types
    assert "sync_completed" in event_types
    assert "order_fetched" in event_types
    assert "invoice_created" in event_types
    
    # Check event structure
    first_event = events[0]
    assert "timestamp" in first_event
    assert "event_type" in first_event
    assert "execution_id" in first_event
    assert "payload" in first_event


@pytest.mark.asyncio
async def test_get_execution_events_not_found(test_client: TestClient):
    """Test GET /api/v1/executions/{execution_id}/events with non-existent ID."""
    fake_id = str(uuid4())
    
    response = test_client.get(f"/api/v1/executions/{fake_id}/events")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execution_with_failed_invoice(test_client: TestClient):
    """Test execution summary with failed invoice."""
    execution_id = str(ExecutionID.generate().value)
    session_factory = get_session_factory()
    uow = create_uow(session_factory)
    
    async with uow:
        event_store = EventStore(uow._session)
        
        # Create events with failed invoice
        sync_started = SyncStartedEvent(
            aggregate_id=f"sync-{execution_id}",
            execution_id=execution_id,
            marketplace="amazon",
        )
        await event_store.append(sync_started)
        
        invoice_failed = InvoiceFailedEvent(
            aggregate_id="112-9999999-9999999",
            execution_id=execution_id,
            order_id="112-9999999-9999999",
            error_message="Odoo API error",
            error_type="invoice_creation",
        )
        await event_store.append(invoice_failed)
        
        sync_completed = SyncCompletedEvent(
            aggregate_id=f"sync-{execution_id}",
            execution_id=execution_id,
            marketplace="amazon",
            total_orders=1,
            successful=0,
            failed=1,
            invoices_created=0,
            invoices_failed=1,
        )
        await event_store.append(sync_completed)
        
        await uow.commit()
    
    response = test_client.get(f"/api/v1/executions/{execution_id}")
    
    assert response.status_code == 200
    body = response.json()
    
    assert body["status"] == "completed_with_errors"
    assert body["invoices_failed"] == 1
    assert body["failed"] == 1
