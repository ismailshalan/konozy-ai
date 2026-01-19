"""
Amazon order sync endpoints.

Provides REST API for syncing Amazon orders to Odoo.
"""
from fastapi import APIRouter, Depends, HTTPException, status
import logging

from core.application.services.amazon_sync_service import AmazonSyncService
from core.application.dtos.sync_dto import (
    OrderSyncRequestDTO,
    OrderSyncResponseDTO,
    BatchSyncRequestDTO,
    BatchSyncResponseDTO,
)
from api.dependencies import get_amazon_sync_service


logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# SYNC SINGLE ORDER
# =============================================================================

@router.post(
    "/sync",
    response_model=OrderSyncResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Sync single Amazon order",
    description="""
    Sync a single Amazon order to Odoo.
    
    **Workflow:**
    1. Extract financial breakdown from Amazon Financial Events
    2. Validate financials (balance equation)
    3. Create Order entity
    4. Save to database
    5. Create Odoo invoice
    6. Send notifications
    
    **Dry Run Mode:**
    Set `dry_run=true` to validate without creating invoice or saving to database.
    """
)
async def sync_amazon_order(
    request: OrderSyncRequestDTO,
    service: AmazonSyncService = Depends(get_amazon_sync_service)
):
    """
    Sync single Amazon order to Odoo.
    
    **Request Body:**
    - `amazon_order_id`: Amazon Order ID (format: XXX-XXXXXXX-XXXXXXX)
    - `financial_events`: Amazon Financial Events API response
    - `buyer_email`: Optional buyer email for partner lookup
    - `dry_run`: If true, validates without persisting
    
    **Returns:**
    - Sync response with execution ID, invoice ID, and financial data
    """
    logger.info(f"API: Sync order request: {request.amazon_order_id}")
    
    try:
        # Execute sync
        response = await service.sync_single_order(
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


# =============================================================================
# SYNC BATCH
# =============================================================================

@router.post(
    "/sync-batch",
    response_model=BatchSyncResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Sync multiple Amazon orders",
    description="""
    Sync multiple Amazon orders in batch.
    
    **Features:**
    - Process multiple orders in parallel
    - Continue on error (configurable)
    - Batch statistics and summary
    - Dry run mode support
    """
)
async def sync_amazon_orders_batch(
    request: BatchSyncRequestDTO,
    service: AmazonSyncService = Depends(get_amazon_sync_service)
):
    """
    Sync multiple Amazon orders in batch.
    
    **Request Body:**
    - `orders`: List of order sync requests
    - `continue_on_error`: If true, continues even if some orders fail
    - `dry_run`: If true, validates all orders without persisting
    
    **Returns:**
    - Batch response with individual results and statistics
    """
    logger.info(f"API: Batch sync request: {len(request.orders)} orders")
    
    try:
        import time
        start_time = time.time()
        
        # Prepare orders data
        orders_data = [
            {
                "order_id": order.amazon_order_id,
                "financial_events": order.financial_events,
                "buyer_email": order.buyer_email
            }
            for order in request.orders
        ]
        
        # Execute batch sync
        responses = await service.sync_multiple_orders(
            orders_data=orders_data,
            continue_on_error=request.continue_on_error,
            dry_run=request.dry_run
        )
        
        # Get statistics
        stats = await service.get_sync_statistics(responses)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Convert responses to DTOs
        result_dtos = [
            OrderSyncResponseDTO(
                execution_id=str(resp.execution_id.value),
                order_id=resp.order_id.value,
                success=resp.success,
                principal_amount=float(resp.principal_amount) if resp.principal_amount else None,
                net_proceeds=float(resp.net_proceeds) if resp.net_proceeds else None,
                odoo_invoice_id=resp.odoo_invoice_id,
                error=resp.error,
                error_details=resp.error_details,
                timestamp=resp.timestamp
            )
            for resp in responses
        ]
        
        # Return batch response
        return BatchSyncResponseDTO(
            total_orders=stats['total_orders'],
            successful=stats['successful'],
            failed=stats['failed'],
            results=result_dtos,
            execution_time_seconds=execution_time
        )
    
    except Exception as e:
        logger.error(f"Batch sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch sync failed: {str(e)}"
        )
