"""
Odoo Financial Mapper - Converts Domain FinancialBreakdown to Odoo Invoice Lines.

CRITICAL: This mapper must produce IDENTICAL Odoo invoice structure to legacy system.
Any deviation in account mapping, analytic tags, or line structure = MISSION FAILURE.

Reference: docs/LEGACY_SYSTEM_ANALYSIS.md section "Odoo Invoice Creation"
"""
from typing import Dict, Any, List, Optional, Callable
from decimal import Decimal
import logging

from core.domain.value_objects.financial import FinancialBreakdown, FinancialLine
from core.domain.entities.order import Order
from core.infrastructure.adapters.amazon.fee_config import PRINCIPAL_MAPPING

logger = logging.getLogger(__name__)


# ==============================================================================
# PRODUCTION ODOO CONFIGURATION (FROM LEGACY SYSTEM)
# ==============================================================================

# TODO: Load from environment variable or config file
# Legacy system uses AMAZON_JOURNAL_ID from environment
AMAZON_JOURNAL_ID = 25  # TODO: Replace with actual production value from env/config

# Tax configuration - Amazon invoices use Zero Rated (no taxes)
TAX_IDS_ZERO_RATED = []  # Empty list = no taxes (Zero Rated)


class OdooFinancialMapper:
    """
    Maps Domain FinancialBreakdown to Odoo Invoice Lines format.
    
    This mapper converts the domain financial model into Odoo's invoice line
    structure, applying account mappings, analytic tags, and product links.
    
    CRITICAL: Must match legacy system's invoice structure EXACTLY.
    
    Usage:
        mapper = OdooFinancialMapper()
        invoice_lines = mapper.to_invoice_lines(
            financial_breakdown=order.financial_breakdown,
            order=order,
            product_lookup=lambda sku: product_id
        )
        invoice_header = mapper.to_invoice_header(order, journal_id=AMAZON_JOURNAL_ID)
    """
    
    @staticmethod
    def to_invoice_lines(
        breakdown: FinancialBreakdown,
        sku_to_principal: Dict[str, Decimal],
        product_lookup: Optional[Callable[[str], Optional[int]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert FinancialBreakdown to Odoo invoice lines.
        
        Supports multi-item orders with SKU-level principal breakdown.
        
        Args:
            breakdown: Complete financial breakdown from Amazon
            sku_to_principal: Mapping of SKU to principal amount
                             Example: {"SKU-A": Decimal("100.00"), "SKU-B": Decimal("200.00")}
            product_lookup: Optional function to get Odoo product_id from SKU
        
        Returns:
            List of invoice line dictionaries ready for Odoo XML-RPC
        
        Example:
            >>> breakdown = FinancialBreakdown(...)
            >>> sku_to_principal = {"SKU-A": Decimal("100.00")}
            >>> lines = OdooFinancialMapper.to_invoice_lines(breakdown, sku_to_principal)
            >>> len(lines)  # Principal + fees/charges
            3
        
        Invoice line structure:
            - Principal lines (one per SKU)
            - Financial lines (fees, charges, promos)
        """
        if not breakdown:
            raise ValueError("Financial breakdown is required")
        
        lines: List[Dict[str, Any]] = []
        
        # =========================================================================
        # PRINCIPAL LINES (Revenue) - One per SKU
        # =========================================================================
        for sku, principal_amount in sku_to_principal.items():
            line_dict = {
                "name": f"Sales Revenue - {sku}",
                "quantity": 1.0,
                "price_unit": float(principal_amount),
                "account_id": PRINCIPAL_MAPPING.account_id,
                "tax_ids": TAX_IDS_ZERO_RATED,
            }
            
            # Lookup product if function provided
            if product_lookup:
                try:
                    product_id = product_lookup(sku)
                    if product_id:
                        line_dict["product_id"] = product_id
                except Exception as e:
                    logger.warning(
                        f"Product lookup failed for SKU {sku}: {e}. "
                        f"Creating line without product link."
                    )
            
            lines.append(line_dict)
        
        # =========================================================================
        # FINANCIAL LINES (Fees, Charges, Promos)
        # =========================================================================
        for financial_line in breakdown.financial_lines:
            line_dict = {
                "name": financial_line.description,
                "quantity": 1.0,
                "price_unit": float(financial_line.amount.amount),
                "tax_ids": TAX_IDS_ZERO_RATED,
            }
            
            # Add account mapping if available
            if financial_line.odoo_mapping:
                line_dict["account_id"] = financial_line.odoo_mapping.account_id
                
                # Add analytic distribution (Odoo 19 format)
                if financial_line.odoo_mapping.analytic_account_id:
                    line_dict["analytic_distribution"] = {
                        str(financial_line.odoo_mapping.analytic_account_id): 100.0
                    }
            
            lines.append(line_dict)
        
        logger.info(f"[ODOO_MAPPER] Built {len(lines)} invoice lines")
        
        return lines
    
    @staticmethod
    def _build_principal_line(
        financial_breakdown: FinancialBreakdown,
        order: Order,
        product_lookup: Optional[Callable[[str], int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Build principal (revenue) invoice line.
        
        Principal represents the base sales revenue before fees and charges.
        Uses PRINCIPAL_MAPPING account (1075 - Revenue account).
        
        Args:
            financial_breakdown: Financial breakdown
            order: Order entity (for SKU/product lookup)
            product_lookup: Optional product lookup function
        
        Returns:
            Invoice line dict for principal, or None if principal is zero
        """
        principal = financial_breakdown.principal
        
        # Skip if principal is zero
        if principal.amount == Decimal("0.00"):
            logger.warning("[ODOO_MAPPER] Principal is zero - skipping principal line")
            return None
        
        # Get SKU from first order item (for product linking)
        # TODO: Handle multi-item orders - may need multiple principal lines
        product_id = None
        sku = None
        
        if order.items:
            sku = order.items[0].sku
            if product_lookup:
                try:
                    product_id = product_lookup(sku)
                    logger.debug(f"[ODOO_MAPPER] Linked principal to product {product_id} (SKU: {sku})")
                except Exception:
                    logger.warning(f"[ODOO_MAPPER] Product lookup failed for SKU: {sku} - continuing without product link")
        
        # Build line dict
        line: Dict[str, Any] = {
            "name": f"Sales Revenue - {sku}" if sku else "Sales Revenue",
            "quantity": 1,
            "price_unit": float(principal.amount),
            "account_id": PRINCIPAL_MAPPING.account_id,  # Revenue account (1075)
            "tax_ids": TAX_IDS_ZERO_RATED,  # Zero Rated - no taxes
        }
        
        if product_id:
            line["product_id"] = product_id
        
        # Note: Principal typically doesn't have analytic account in legacy system
        # If needed in future, check PRINCIPAL_MAPPING.analytic_account_id
        
        return line
    
    @staticmethod
    def _build_financial_line(
        financial_line: FinancialLine
    ) -> Dict[str, Any]:
        """
        Build invoice line from FinancialLine (fee, charge, or promotion).
        
        Each FinancialLine maps 1:1 to an invoice line.
        Uses account and analytic mapping from FinancialLine.odoo_mapping.
        
        Args:
            financial_line: Domain financial line
        
        Returns:
            Invoice line dict ready for Odoo
        """
        line: Dict[str, Any] = {
            "name": financial_line.description,
            "quantity": 1,
            "price_unit": float(financial_line.amount.amount),
            "tax_ids": TAX_IDS_ZERO_RATED,  # Zero Rated - no taxes
        }
        
        # Account mapping (CRITICAL: from odoo_mapping)
        if financial_line.odoo_mapping:
            line["account_id"] = financial_line.odoo_mapping.account_id
            
            # Analytic account (Odoo 19 uses analytic_distribution format)
            if financial_line.odoo_mapping.analytic_account_id:
                line["analytic_distribution"] = {
                    str(financial_line.odoo_mapping.analytic_account_id): 100.0
                }
        else:
            logger.warning(
                f"[ODOO_MAPPER] Financial line '{financial_line.description}' "
                f"has no odoo_mapping - account_id will be missing"
            )
        
        return line
    
    @staticmethod
    def to_invoice_header(
        order: Order,
        journal_id: Optional[int] = None,
        currency_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build Odoo invoice header/values.
        
        Creates the invoice header dict for account.move creation.
        Includes journal, date, reference, and currency.
        
        Args:
            order: Order entity
            journal_id: Optional journal ID (defaults to AMAZON_JOURNAL_ID)
            currency_code: Optional currency code (defaults to financial breakdown currency, then "EGP")
        
        Returns:
            Invoice header dict for account.move creation.
            Format: {
                "move_type": "out_invoice",
                "journal_id": int,
                "invoice_date": str (ISO format),
                "ref": str,
                "currency_id": int (optional, TODO: implement currency lookup)
            }
        """
        # Determine invoice date (from posted_date if available, else purchase_date)
        invoice_date = (
            order.financial_breakdown.posted_date.date()
            if order.financial_breakdown and order.financial_breakdown.posted_date
            else order.purchase_date.date()
        )
        
        # Determine currency
        # TODO: Implement currency_id lookup from currency_code
        # For now, currency_id is not set (Odoo will use journal default)
        currency_code = currency_code or (
            order.financial_breakdown.principal.currency
            if order.financial_breakdown
            else "EGP"
        )
        
        header: Dict[str, Any] = {
            "move_type": "out_invoice",
            "invoice_date": invoice_date.isoformat(),
            "ref": f"Amazon Order {order.order_id.value}",
            "journal_id": journal_id or AMAZON_JOURNAL_ID,
        }
        
        # TODO: Add currency_id when currency lookup is implemented
        # currency_id = lookup_currency_id(currency_code)
        # if currency_id:
        #     header["currency_id"] = currency_id
        
        return header
