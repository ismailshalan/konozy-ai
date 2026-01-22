"""
Orders management endpoints.

Provides CRUD operations for orders.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import logging

from core.domain.value_objects import OrderNumber
from api.dependencies import get_order_repository


logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# LIST ORDERS (FIXED)
# =============================================================================

@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List all orders",
    description="Get list of all orders in the system"
)
async def list_orders(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of orders to return"),
    offset: int = Query(default=0, ge=0, description="Number of orders to skip"),
    repository=Depends(get_order_repository)
):
    """
    List all orders with pagination.
    
    **Query Parameters:**
    - `limit`: Maximum orders to return (1-1000, default: 100)
    - `offset`: Number of orders to skip (default: 0)
    
    **Returns:**
    - List of orders with basic information
    """
    try:
        # Get all orders
        all_orders = repository.get_all()
        
        # Apply pagination
        paginated_orders = all_orders[offset:offset + limit]
        
        return {
            "total": len(all_orders),
            "limit": limit,
            "offset": offset,
            "count": len(paginated_orders),
            "orders": [
                {
                    "order_id": order.order_id.value,
                    "marketplace": order.marketplace,
                    "purchase_date": order.purchase_date.isoformat() if order.purchase_date else None,
                    "status": order.order_status,
                    "principal": float(order.financial_breakdown.principal.amount) if order.financial_breakdown else None,
                    "net_proceeds": float(order.financial_breakdown.net_proceeds.amount) if order.financial_breakdown else None,
                }
                for order in paginated_orders
            ]
        }
    
    except Exception as e:
        logger.error(f"List orders failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list orders: {str(e)}"
        )


# =============================================================================
# GET ORDER BY ID
# =============================================================================

@router.get(
    "/{order_id}",
    status_code=status.HTTP_200_OK,
    summary="Get order by ID",
    description="Get detailed information about a specific order"
)
async def get_order(
    order_id: str,
    repository=Depends(get_order_repository)
):
    """
    Get order by ID.
    
    **Parameters:**
    - `order_id`: Amazon/Noon order ID
    
    **Returns:**
    - Detailed order information including financial breakdown
    """
    try:
        # Try to create OrderNumber - if validation fails, treat as not found
        try:
            order_number = OrderNumber(value=order_id)
        except ValueError:
            # Invalid order ID format - treat as not found (404 instead of 400)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found: {order_id}"
            )
        
        order = await repository.get_by_id(order_number)
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order not found: {order_id}"
            )
        
        # Build response
        response = {
            "order_id": order.order_id.value,
            "marketplace": order.marketplace,
            "purchase_date": order.purchase_date.isoformat() if order.purchase_date else None,
            "buyer_email": order.buyer_email,
            "status": order.order_status,
        }
        
        # Add financial breakdown if available
        if order.financial_breakdown:
            response["financial_breakdown"] = {
                "principal": {
                    "amount": float(order.financial_breakdown.principal.amount),
                    "currency": order.financial_breakdown.principal.currency
                },
                "net_proceeds": {
                    "amount": float(order.financial_breakdown.net_proceeds.amount),
                    "currency": order.financial_breakdown.net_proceeds.currency
                },
                "financial_lines": [
                    {
                        "type": line.line_type,
                        "description": line.description,
                        "amount": float(line.amount.amount),
                        "sku": line.sku
                    }
                    for line in order.financial_breakdown.financial_lines
                ]
            }
        
        # Add execution ID if available
        if order.execution_id:
            response["execution_id"] = str(order.execution_id.value)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get order failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order: {str(e)}"
        )
# =============================================================================
# SYNC ORDERS ENDPOINT
# =============================================================================

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from core.domain.value_objects import ExecutionID
from api.dependencies import get_amazon_sync_service
from core.application.services.amazon_sync_service import AmazonSyncService


class SyncOrdersRequest(BaseModel):
    """Request model for order sync endpoint."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    marketplace: str = "amazon"


@router.post(
    "/sync",
    status_code=status.HTTP_200_OK,
    summary="Trigger order sync",
    description="""
    Trigger order synchronization from marketplace.
    
    This endpoint generates an execution_id and initiates the sync process.
    The actual sync may run asynchronously depending on the implementation.
    
    **Parameters:**
    - `start_date`: Optional ISO 8601 date string for filtering orders
    - `end_date`: Optional ISO 8601 date string for filtering orders
    - `marketplace`: Marketplace name (default: "amazon")
    
    **Returns:**
    - Execution ID for tracking the sync operation
    - Status confirmation
    """
)
async def sync_orders(
    request: Optional[SyncOrdersRequest] = None,
    service: AmazonSyncService = Depends(get_amazon_sync_service)
):
    """
    Trigger order synchronization.
    
    This endpoint generates an execution_id and initiates the sync process.
    """
    try:
        # Generate execution_id
        execution_id = ExecutionID.generate()
        
        # Log start of request
        logger.info(
            f"[{execution_id}] Order sync request received - "
            f"marketplace={request.marketplace if request else 'amazon'}, "
            f"start_date={request.start_date if request else None}, "
            f"end_date={request.end_date if request else None}"
        )
        
        # Parse dates if provided
        start_date = None
        end_date = None
        
        if request:
            if request.start_date:
                try:
                    start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                    logger.info(f"[{execution_id}] Parsed start_date: {start_date}")
                except ValueError as e:
                    logger.warning(f"[{execution_id}] Invalid start_date format: {e}")
            
            if request.end_date:
                try:
                    end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                    logger.info(f"[{execution_id}] Parsed end_date: {end_date}")
                except ValueError as e:
                    logger.warning(f"[{execution_id}] Invalid end_date format: {e}")
        
        # Log generated execution_id
        logger.info(f"[{execution_id}] Execution ID generated: {execution_id}")
        
        # Note: The actual sync logic would be triggered here
        # For now, we return the execution_id to indicate the sync has started
        # In a full implementation, this would trigger a background job or async task
        
        # Parse dates if provided
        start_date_obj = None
        end_date_obj = None
        
        if request:
            if request.start_date:
                try:
                    start_date_obj = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
                    logger.info(f"[{execution_id}] Parsed start_date: {start_date_obj}")
                except ValueError as e:
                    logger.warning(f"[{execution_id}] Invalid start_date format: {e}")
            
            if request.end_date:
                try:
                    end_date_obj = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
                    logger.info(f"[{execution_id}] Parsed end_date: {end_date_obj}")
                except ValueError as e:
                    logger.warning(f"[{execution_id}] Invalid end_date format: {e}")
        
        # Call the real sync service
        logger.info(f"[{execution_id}] Calling AmazonSyncService.sync_orders()")
        sync_result = await service.sync_orders(
            start_date=start_date_obj,
            end_date=end_date_obj,
            execution_id=execution_id,
        )
        
        # Log final confirmation
        logger.info(
            f"[{execution_id}] Order sync completed - "
            f"total_orders={sync_result.get('total_orders', 0)}, "
            f"successful={sync_result.get('successful', 0)}, "
            f"invoices={sync_result.get('created_invoices', 0)}"
        )
        
        # Return response with sync results
        return {
            "status": "completed",
            "execution_id": sync_result.get("execution_id", str(execution_id)),
            "message": "Order sync completed successfully",
            "marketplace": request.marketplace if request else "amazon",
            "total_orders": sync_result.get("total_orders", 0),
            "created_invoices": sync_result.get("created_invoices", 0),
            "failed_items": sync_result.get("failed_items", []),
            "successful": sync_result.get("successful", 0),
            "start_date": request.start_date if request and request.start_date else None,
            "end_date": request.end_date if request and request.end_date else None,
        }
    
    except Exception as e:
        logger.error(f"Sync orders failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start order sync: {str(e)}"
        )
