"""
Financial value objects for marketplace fee handling.

CRITICAL: This file must contain ZERO imports from:
- sqlalchemy
- pydantic
- fastapi
"""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

# Forward reference for Money - will be imported at runtime
# from .value_objects import Money


class AmazonFeeType(Enum):
    """
    Amazon Financial Events API fee types.
    
    THESE VALUES MUST MATCH PRODUCTION EXACTLY.
    Source: LEGACY_SYSTEM_ANALYSIS.md
    """
    FBA_FULFILLMENT = "FBAPerUnitFulfillmentFee"
    COMMISSION = "Commission"
    REFUND_COMMISSION = "RefundCommission"
    SHIPPING_CHARGE = "ShippingCharge"
    PROMO_REBATE = "PROMO_REBATE"
    STORAGE_FEE = "StorageFee"


@dataclass(frozen=True)
class OdooAccountMapping:
    """
    Maps fee type to Odoo chart of accounts.
    
    CRITICAL: These IDs are PRODUCTION values from legacy system.
    DO NOT CHANGE without coordination with accounting team.
    """
    account_id: int                        # Odoo account.account ID
    analytic_account_id: Optional[int] = None     # Odoo analytic account ID
    
    def __post_init__(self):
        if self.account_id <= 0:
            raise ValueError(f"Invalid account_id: {self.account_id}")
        if self.analytic_account_id is not None and self.analytic_account_id <= 0:
            raise ValueError(f"Invalid analytic_account_id: {self.analytic_account_id}")


@dataclass(frozen=True)
class FinancialLine:
    """
    Single financial component (fee, charge, or promotion).
    
    Each FinancialLine maps 1:1 to an Odoo invoice line.
    
    Attributes:
        line_type: Category - "fee", "charge", "promo", "principal"
        fee_type: Amazon fee classification (None for principal)
        amount: Monetary amount (negative for expenses, positive for revenue)
        description: Human-readable description for invoice
        sku: Product SKU (for traceability)
        odoo_mapping: Account and analytic account IDs
    """
    line_type: str                         # "fee", "charge", "promo", "principal"
    amount: 'Money'                        # Import from value_objects.py
    description: str
    fee_type: Optional[AmazonFeeType] = None
    sku: Optional[str] = None
    odoo_mapping: Optional[OdooAccountMapping] = None
    
    def __post_init__(self):
        valid_types = ["fee", "charge", "promo", "principal"]
        if self.line_type not in valid_types:
            raise ValueError(f"Invalid line_type: {self.line_type}")


@dataclass(frozen=True)
class FinancialBreakdown:
    """
    Complete financial decomposition of an order.
    
    Represents the EXACT structure extracted from Amazon Financial Events API.
    
    Balance Equation (MUST ALWAYS HOLD):
        principal + sum(financial_lines.amount) = net_proceeds
    
    Tolerance: ±0.01 (one cent) for floating point rounding
    """
    principal: 'Money'                     # Item revenue (before fees)
    financial_lines: List[FinancialLine]  # All fees, charges, promos
    net_proceeds: 'Money'                  # Seller's actual proceeds
    posted_date: Optional[datetime] = None # For invoice_date
    
    def validate_balance(self) -> bool:
        """
        Validate financial balance equation.
        
        Returns:
            True if balance equation holds within tolerance
        """
        TOLERANCE = Decimal("0.01")
        
        total_lines = sum(
            line.amount.amount for line in self.financial_lines
        )
        calculated_net = self.principal.amount + total_lines
        difference = abs(calculated_net - self.net_proceeds.amount)
        
        return difference <= TOLERANCE
    
    def get_fees(self) -> List[FinancialLine]:
        """Get only fee lines (expenses)."""
        return [line for line in self.financial_lines if line.line_type == "fee"]
    
    def get_charges(self) -> List[FinancialLine]:
        """Get only charge lines (additional revenue)."""
        return [line for line in self.financial_lines if line.line_type == "charge"]
    
    def get_promos(self) -> List[FinancialLine]:
        """Get only promotion/rebate lines."""
        return [line for line in self.financial_lines if line.line_type == "promo"]
