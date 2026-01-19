"""
DTOs for order sync operations.

Fixed for Pydantic V2 compatibility.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# =============================================================================
# REQUEST DTOs
# =============================================================================

class OrderSyncRequestDTO(BaseModel):
    """Request DTO for syncing single order."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amazon_order_id": "407-1263947-9146736",
                "financial_events": {
                    "ShipmentEventList": []
                },
                "dry_run": False
            }
        }
    )
    
    amazon_order_id: str = Field(
        ...,
        description="Amazon Order ID",
        examples=["407-1263947-9146736"]
    )
    
    financial_events: Dict[str, Any] = Field(
        ...,
        description="Amazon Financial Events API response"
    )
    
    buyer_email: Optional[str] = Field(
        default=None,
        description="Buyer email for Odoo partner lookup"
    )
    
    dry_run: bool = Field(
        default=False,
        description="If true, validates without creating invoice"
    )
    
    @field_validator('amazon_order_id')
    @classmethod
    def validate_order_id(cls, v: str) -> str:
        """Validate Amazon order ID format."""
        if not v or len(v) < 10:
            raise ValueError("Invalid Amazon order ID")
        
        parts = v.split('-')
        if len(parts) != 3:
            raise ValueError("Amazon order ID must have format: XXX-XXXXXXX-XXXXXXX")
        
        return v


class OrderSyncResponseDTO(BaseModel):
    """Response DTO for order sync operation."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "execution_id": "123e4567-e89b-12d3-a456-426614174000",
                "order_id": "407-1263947-9146736",
                "success": True,
                "principal_amount": "198.83",
                "net_proceeds": "150.96",
                "odoo_invoice_id": 12345,
                "timestamp": "2026-01-15T10:30:00Z"
            }
        }
    )
    
    execution_id: str = Field(..., description="Unique execution ID for tracing")
    order_id: str = Field(..., description="Amazon/Noon order ID")
    success: bool = Field(..., description="Whether sync was successful")
    
    principal_amount: Optional[Decimal] = Field(default=None, description="Total principal amount")
    net_proceeds: Optional[Decimal] = Field(default=None, description="Net proceeds after fees")
    odoo_invoice_id: Optional[int] = Field(default=None, description="Created invoice ID in Odoo")
    
    error: Optional[str] = Field(default=None, description="Error message if sync failed")
    error_details: Optional[str] = Field(default=None, description="Detailed error information")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class BatchSyncRequestDTO(BaseModel):
    """Request DTO for batch order sync."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "orders": [],
                "continue_on_error": True,
                "dry_run": False
            }
        }
    )
    
    orders: List[OrderSyncRequestDTO] = Field(
        ...,
        description="List of orders to sync",
        min_length=1,
        max_length=100
    )
    
    continue_on_error: bool = Field(
        default=True,
        description="If true, continues processing even if some orders fail"
    )
    
    dry_run: bool = Field(
        default=False,
        description="If true, validates all orders without creating invoices"
    )


class BatchSyncResponseDTO(BaseModel):
    """Response DTO for batch order sync."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_orders": 10,
                "successful": 9,
                "failed": 1,
                "results": [],
                "execution_time_seconds": 15.5,
                "timestamp": "2026-01-15T10:30:00Z"
            }
        }
    )
    
    total_orders: int = Field(..., description="Total number of orders in batch")
    successful: int = Field(..., description="Number of successfully synced orders")
    failed: int = Field(..., description="Number of failed orders")
    
    results: List[OrderSyncResponseDTO] = Field(..., description="Individual sync results")
    
    execution_time_seconds: float = Field(..., description="Total execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Batch completion timestamp")
