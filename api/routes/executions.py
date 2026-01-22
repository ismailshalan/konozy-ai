"""
Execution monitoring endpoints.

Provides endpoints to query sync execution status and events.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.infrastructure.database.config import get_session
from core.infrastructure.database.event_store import EventStore
from core.domain.events.order_events import (
    SyncStartedEvent,
    SyncCompletedEvent,
    OrderFetchedEvent,
    InvoiceCreatedEvent,
    InvoiceFailedEvent,
)
from core.domain.events.base import DomainEvent


router = APIRouter(prefix="/executions", tags=["executions"])


def get_event_store(session: AsyncSession = Depends(get_session)) -> EventStore:
    """Get event store instance."""
    return EventStore(session)


@router.get(
    "/{execution_id}",
    status_code=status.HTTP_200_OK,
    summary="Get execution summary",
    description="""
    Get high-level summary of a sync execution.
    
    Returns status, statistics, and timestamps for the execution.
    """
)
async def get_execution_summary(
    execution_id: str,
    event_store: EventStore = Depends(get_event_store),
) -> Dict[str, Any]:
    """
    Get execution summary by execution_id.
    
    Args:
        execution_id: Execution ID to query
        event_store: Event store instance
        
    Returns:
        Execution summary with status and statistics
    """
    try:
        # Validate UUID format
        UUID(execution_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_id format: {execution_id}"
        )
    
    # Get all events for this execution
    events = await event_store.get_events_by_execution(execution_id)
    
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    # Find SyncStartedEvent and SyncCompletedEvent
    sync_started: Optional[SyncStartedEvent] = None
    sync_completed: Optional[SyncCompletedEvent] = None
    
    # Count order-level events
    orders_fetched = 0
    invoices_created = 0
    invoices_failed = 0
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    for event in events:
        if isinstance(event, SyncStartedEvent):
            sync_started = event
            started_at = event.occurred_at
        elif isinstance(event, SyncCompletedEvent):
            sync_completed = event
            completed_at = event.occurred_at
            invoices_created = event.invoices_created
            invoices_failed = event.invoices_failed
        elif isinstance(event, OrderFetchedEvent):
            orders_fetched += 1
        elif isinstance(event, InvoiceCreatedEvent):
            invoices_created += 1
        elif isinstance(event, InvoiceFailedEvent):
            invoices_failed += 1
    
    # Determine status
    if sync_completed:
        if sync_completed.failed > 0:
            exec_status = "completed_with_errors"
        else:
            exec_status = "completed"
    elif sync_started:
        exec_status = "running"
    else:
        exec_status = "unknown"
    
    # Get marketplace from sync_started or default
    marketplace = sync_started.marketplace if sync_started else "amazon"
    
    # Get totals from sync_completed if available, otherwise count events
    total_orders = sync_completed.total_orders if sync_completed else orders_fetched
    successful = sync_completed.successful if sync_completed else 0
    failed = sync_completed.failed if sync_completed else 0
    
    return {
        "execution_id": execution_id,
        "status": exec_status,
        "marketplace": marketplace,
        "total_orders": total_orders,
        "successful": successful,
        "failed": failed,
        "invoices_created": invoices_created,
        "invoices_failed": invoices_failed,
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "start_date": sync_started.start_date if sync_started else None,
        "end_date": sync_started.end_date if sync_started else None,
    }


@router.get(
    "/{execution_id}/events",
    status_code=status.HTTP_200_OK,
    summary="Get execution events",
    description="""
    Get detailed event list for an execution.
    
    Returns all events associated with the execution_id, ordered by timestamp.
    """
)
async def get_execution_events(
    execution_id: str,
    event_store: EventStore = Depends(get_event_store),
) -> List[Dict[str, Any]]:
    """
    Get all events for an execution.
    
    Args:
        execution_id: Execution ID to query
        event_store: Event store instance
        
    Returns:
        List of events with timestamps and payloads
    """
    try:
        # Validate UUID format
        UUID(execution_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid execution_id format: {execution_id}"
        )
    
    # Get all events for this execution
    events = await event_store.get_events_by_execution(execution_id)
    
    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    # Convert events to JSON-serializable format
    event_list = []
    for event in events:
        event_dict = {
            "timestamp": event.occurred_at.isoformat(),
            "event_type": event.event_type,
            "aggregate_id": event.aggregate_id,
            "execution_id": event.execution_id,
        }
        
        # Add event-specific payload
        if isinstance(event, SyncStartedEvent):
            event_dict["payload"] = {
                "marketplace": event.marketplace,
                "start_date": event.start_date,
                "end_date": event.end_date,
            }
        elif isinstance(event, SyncCompletedEvent):
            event_dict["payload"] = {
                "marketplace": event.marketplace,
                "total_orders": event.total_orders,
                "successful": event.successful,
                "failed": event.failed,
                "invoices_created": event.invoices_created,
                "invoices_failed": event.invoices_failed,
            }
        elif isinstance(event, OrderFetchedEvent):
            event_dict["payload"] = {
                "order_id": event.order_id,
                "marketplace": event.marketplace,
                "buyer_email": event.buyer_email,
                "purchase_date": event.purchase_date,
            }
        elif isinstance(event, InvoiceCreatedEvent):
            event_dict["payload"] = {
                "order_id": event.order_id,
                "invoice_id": event.invoice_id,
                "partner_id": event.partner_id,
                "invoice_lines_count": event.invoice_lines_count,
            }
        elif isinstance(event, InvoiceFailedEvent):
            event_dict["payload"] = {
                "order_id": event.order_id,
                "error_message": event.error_message,
                "error_type": event.error_type,
            }
        else:
            # Generic event - use event data
            event_dict["payload"] = event._get_event_data() if hasattr(event, '_get_event_data') else {}
        
        event_list.append(event_dict)
    
    return event_list
