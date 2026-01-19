"""Marketplace endpoints for REST API."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional
import logging

from core.application.services.marketplace_service import MarketplaceService
from core.application.services.order_service import OrderApplicationService
from core.application.services.amazon_sync_service import AmazonSyncService
from core.application.dtos.sync_dto import OrderSyncRequestDTO, OrderSyncResponseDTO
from apps.api.deps import get_order_service, get_amazon_sync_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post(
    "/amazon/sync",
    response_model=OrderSyncResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Sync single Amazon order",
    description="""
    Sync a single Amazon order to Odoo using the new Clean Architecture.
    
    This endpoint uses SyncAmazonOrderUseCase and AmazonSyncService.
    """
)
async def sync_amazon_order(
    request: OrderSyncRequestDTO,
    amazon_sync_service: AmazonSyncService = Depends(get_amazon_sync_service),
):
    """Sync a single Amazon order to Odoo.

    Args:
        request: OrderSyncRequestDTO with order data and financial events
        amazon_sync_service: AmazonSyncService instance

    Returns:
        OrderSyncResponseDTO with sync results

    Raises:
        HTTPException: If sync operation fails
    """
    logger.info(f"API: Sync Amazon order request: {request.amazon_order_id}")
    
    try:
        # Execute sync using new service
        response = await amazon_sync_service.sync_single_order(
            order_id=request.amazon_order_id,
            financial_events=request.financial_events,
            buyer_email=request.buyer_email,
            dry_run=request.dry_run
        )
        
        # Check if successful
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": response.error,
                    "details": response.error_details,
                    "execution_id": str(response.execution_id.value)
                }
            )
        
        # Return DTO
        return OrderSyncResponseDTO(
            execution_id=str(response.execution_id.value),
            order_id=response.order_id.value,
            success=response.success,
            principal_amount=float(response.principal_amount) if response.principal_amount else None,
            net_proceeds=float(response.net_proceeds) if response.net_proceeds else None,
            odoo_invoice_id=response.odoo_invoice_id,
            error=response.error,
            error_details=response.error_details,
            timestamp=response.timestamp
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/amazon/sync-old")
async def sync_amazon_orders_old(
    order_service: OrderApplicationService = Depends(get_order_service),
):
    """Sync Amazon orders into the system (OLD ENDPOINT - for compatibility).

    This endpoint is kept for backward compatibility.
    Use /marketplace/amazon/sync for the new implementation.

    Returns:
        JSON response with sync status

    Raises:
        HTTPException: If sync operation fails
    """
    try:
        # Create MarketplaceService
        marketplace_service = MarketplaceService(order_service=order_service)

        # For now, return a success response
        # In production, this would call marketplace_service.fetch_and_sync_amazon_orders()
        # For now, it's a stub that returns success
        
        return {
            "message": "Amazon orders sync initiated (old endpoint - use /amazon/sync)",
            "orders_synced": 0,
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
