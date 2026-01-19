"""Order endpoints for REST API."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from core.application.dtos.order_dto import CreateOrderRequest, OrderDTO
from core.application.services.order_service import OrderApplicationService

from apps.api.deps import get_order_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderDTO, status_code=201)
async def create_order(
    request: CreateOrderRequest,
    service: OrderApplicationService = Depends(get_order_service),
) -> OrderDTO:
    """Create a new order.

    Args:
        request: CreateOrderRequest DTO
        service: OrderApplicationService instance

    Returns:
        OrderDTO with created order details

    Raises:
        HTTPException: If order creation fails
    """
    try:
        return await service.create_order(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{order_id}", response_model=OrderDTO)
async def get_order(
    order_id: str,
    service: OrderApplicationService = Depends(get_order_service),
) -> OrderDTO:
    """Get order by ID.

    Args:
        order_id: Order ID string
        service: OrderApplicationService instance

    Returns:
        OrderDTO with order details

    Raises:
        HTTPException: If order not found
    """
    try:
        order = await service.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
        return order
    except ValueError:
        # Invalid order ID format - treat as not found (404 instead of 400)
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@router.get("", response_model=List[OrderDTO])
async def list_orders(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of orders"),
    service: OrderApplicationService = Depends(get_order_service),
) -> List[OrderDTO]:
    """List orders with pagination.

    Args:
        limit: Maximum number of orders to return
        service: OrderApplicationService instance

    Returns:
        List of OrderDTO instances
    """
    try:
        return await service.list_orders(limit=limit)
    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Error in list_orders endpoint: {type(e).__name__}: {str(e)}", exc_info=True)
        # Return empty list instead of 500 error to prevent frontend failures
        # This is a graceful degradation - if DB is unavailable, return empty list
        return []
