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
# SYNC ORDERS (LEGACY ENDPOINT FOR TEST COMPATIBILITY)
# =============================================================================

from api.dependencies import get_order_service
from core.application.services.amazon_sync_service import AmazonSyncService

@router.post(
    "/sync",
    status_code=status.HTTP_200_OK,
    summary="Trigger full order sync",
    description="Runs full Amazon order sync and returns summary"
)
async def sync_orders(
    service: AmazonSyncService = Depends(get_order_service)
):
    """
    Legacy-compatible sync endpoint used by integration tests.
    """
    try:
        result = service.sync()
        return {
            "status": "ok",
            "synced": result
        }
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync orders: {str(e)}"
        )
