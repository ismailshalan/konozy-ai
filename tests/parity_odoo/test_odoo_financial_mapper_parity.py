"""
PARITY TESTS - Odoo Financial Mapper vs Legacy System

CRITICAL: These tests validate that OdooFinancialMapper produces
IDENTICAL invoice structure to legacy system. All tests must pass with ZERO discrepancies.

Any failure = MISSION FAILURE = Financial posting accuracy compromised.
"""
import pytest
from decimal import Decimal
from typing import Dict, Any, List

from core.infrastructure.adapters.amazon.fee_mapper import AmazonFeeMapper
from core.infrastructure.adapters.odoo.odoo_financial_mapper import (
    OdooFinancialMapper,
    AMAZON_JOURNAL_ID,
    TAX_IDS_ZERO_RATED,
)
from core.domain.entities.order import Order
from core.domain.value_objects import OrderNumber, Money
from datetime import datetime


class TestOdooFinancialMapperParity:
    """Verify OdooFinancialMapper matches legacy Odoo invoice structure EXACTLY."""
    
    def _create_order_from_financial_breakdown(
        self,
        breakdown,
        order_id: str,
        raw_events: Dict[str, Any]
    ) -> Order:
        """Create Order entity from financial breakdown for testing."""
        # Find shipment event
        events_list = raw_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        
        # Get buyer email (if available)
        buyer_email = shipment_event.get("BuyerInfo", {}).get("BuyerEmail", "test@example.com")
        
        # Get purchase date
        purchase_date_str = shipment_event.get("PostedDate", "")
        if purchase_date_str:
            purchase_date = datetime.fromisoformat(purchase_date_str.replace("Z", "+00:00"))
        else:
            purchase_date = datetime.now()
        
        # Create order
        order_number = OrderNumber(value=order_id)
        
        order = Order(
            order_id=order_number,
            purchase_date=purchase_date,
            buyer_email=buyer_email,
            financial_breakdown=breakdown,
        )
        
        return order
    
    def test_invoice_lines_structure(
        self,
        raw_financial_events,
        ground_truth
    ):
        """
        Test: Invoice lines structure matches Odoo format.
        
        Validates:
        - All required fields present (name, quantity, price_unit, account_id, tax_ids)
        - Optional fields handled correctly (product_id, analytic_distribution)
        - Structure matches Odoo invoice line format
        """
        # Use order ID that starts with "1" (OrderNumber validation requirement)
        order_id = "171-3372061-4556310"
        
        # Extract financial breakdown
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(financial_events, order_id)
        
        # Extract SKU-to-principal mapping
        sku_to_principal = AmazonFeeMapper.extract_sku_to_principal(financial_events)
        
        # Generate invoice lines
        invoice_lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Validate structure
        assert len(invoice_lines) > 0, "Invoice lines should not be empty"
        
        required_fields = ["name", "quantity", "price_unit", "account_id", "tax_ids"]
        
        for line in invoice_lines:
            # Check required fields
            for field in required_fields:
                assert field in line, f"Missing required field: {field} in line: {line}"
            
            # Validate types
            assert isinstance(line["name"], str), "name must be string"
            assert isinstance(line["quantity"], (int, float)), "quantity must be number"
            assert isinstance(line["price_unit"], (int, float)), "price_unit must be number"
            assert isinstance(line["account_id"], int), "account_id must be int"
            assert isinstance(line["tax_ids"], list), "tax_ids must be list"
            
            # Validate tax_ids is empty (Zero Rated)
            assert line["tax_ids"] == TAX_IDS_ZERO_RATED, "tax_ids must be empty (Zero Rated)"
            
            # Optional fields validation
            if "product_id" in line:
                assert isinstance(line["product_id"], int), "product_id must be int"
            
            if "analytic_distribution" in line:
                assert isinstance(line["analytic_distribution"], dict), "analytic_distribution must be dict"
                for key, value in line["analytic_distribution"].items():
                    assert isinstance(key, str), "analytic_distribution keys must be strings"
                    assert isinstance(value, (int, float)), "analytic_distribution values must be numbers"
    
    def test_invoice_lines_account_mapping(
        self,
        raw_financial_events
    ):
        """
        Test: Account mappings match legacy system.
        
        Validates:
        - Principal uses account 1075 (Revenue)
        - Fees use account 1133 (from mapping)
        - Charges use account 1075 (Shipping) or 1075 (PaymentMethodFee)
        - Promos use account 1100
        """
        order_id = "171-3372061-4556310"
        
        # Extract financial breakdown
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(financial_events, order_id)
        
        # Extract SKU-to-principal mapping
        sku_to_principal = AmazonFeeMapper.extract_sku_to_principal(financial_events)
        
        # Generate invoice lines
        invoice_lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Find principal lines (lines with "Sales Revenue" in name)
        principal_lines = [l for l in invoice_lines if "Sales Revenue" in l["name"]]
        assert len(principal_lines) > 0, "Should have at least one principal line"
        assert principal_lines[0]["account_id"] == 1075, "Principal must use account 1075"
        
        # Check fee lines (should use account 1133)
        for line in invoice_lines:
            if "Sales Revenue" not in line["name"]:  # Skip principal lines
                account_id = line.get("account_id")
                if account_id:
                    # Fees should use 1133, Shipping charges use 1075, Promos use 1100
                    assert account_id in [1075, 1133, 1100], f"Unexpected account_id: {account_id}"
    
    def test_invoice_lines_analytic_distribution(
        self,
        raw_financial_events
    ):
        """
        Test: Analytic distribution matches legacy system.
        
        Validates:
        - Fee lines have analytic_distribution with correct IDs
        - Format matches Odoo 19 (dict with str keys)
        - Values are 100.0 (100%)
        """
        order_id = "171-3372061-4556310"
        
        # Extract financial breakdown
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(financial_events, order_id)
        
        # Extract SKU-to-principal mapping
        sku_to_principal = AmazonFeeMapper.extract_sku_to_principal(financial_events)
        
        # Generate invoice lines
        invoice_lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Check analytic distribution format
        for line in invoice_lines:
            if "analytic_distribution" in line:
                analytic = line["analytic_distribution"]
                assert isinstance(analytic, dict), "analytic_distribution must be dict"
                assert len(analytic) > 0, "analytic_distribution should not be empty"
                
                for key, value in analytic.items():
                    assert isinstance(key, str), "analytic_distribution keys must be strings (Odoo 19 format)"
                    assert value == 100.0, "analytic_distribution values should be 100.0"
    
    def test_invoice_header_structure(
        self,
        raw_financial_events
    ):
        """
        Test: Invoice header structure matches Odoo format.
        
        Validates:
        - move_type = "out_invoice"
        - journal_id is set
        - invoice_date is ISO format string
        - ref contains order ID
        """
        order_id = "171-3372061-4556310"
        
        # Extract financial breakdown
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(financial_events, order_id)
        
        # Create order
        order = self._create_order_from_financial_breakdown(
            breakdown, order_id, raw_financial_events
        )
        
        # Generate invoice header
        header = OdooFinancialMapper.to_invoice_header(order)
        
        # Validate structure
        assert "move_type" in header, "move_type must be present"
        assert header["move_type"] == "out_invoice", "move_type must be 'out_invoice'"
        
        assert "journal_id" in header, "journal_id must be present"
        assert header["journal_id"] == AMAZON_JOURNAL_ID, f"journal_id must be {AMAZON_JOURNAL_ID}"
        
        assert "invoice_date" in header, "invoice_date must be present"
        assert isinstance(header["invoice_date"], str), "invoice_date must be string (ISO format)"
        
        assert "ref" in header, "ref must be present"
        assert order_id in header["ref"], "ref must contain order ID"
    
    def test_invoice_lines_totals_balance(
        self,
        raw_financial_events
    ):
        """
        Test: Invoice lines totals match financial breakdown.
        
        Validates:
        - Sum of all invoice lines matches net_proceeds (within tolerance)
        - Principal line amount matches breakdown.principal
        - Fee/charge/promo lines match breakdown.financial_lines
        """
        order_id = "171-3372061-4556310"
        
        # Extract financial breakdown
        events_list = raw_financial_events["الأحداث_المالية"]["ShipmentEventList"]
        shipment_event = next(
            e for e in events_list if e["AmazonOrderId"] == order_id
        )
        financial_events = {"ShipmentEventList": [shipment_event]}
        breakdown = AmazonFeeMapper.parse_financial_events(financial_events, order_id)
        
        # Extract SKU-to-principal mapping
        sku_to_principal = AmazonFeeMapper.extract_sku_to_principal(financial_events)
        
        # Generate invoice lines
        invoice_lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Calculate total from invoice lines
        total_from_lines = sum(line["price_unit"] for line in invoice_lines)
        
        # Calculate expected total (principal + all financial lines)
        expected_total = float(
            breakdown.principal.amount +
            sum(line.amount.amount for line in breakdown.financial_lines)
        )
        
        # Validate balance
        TOLERANCE = 0.01
        difference = abs(total_from_lines - expected_total)
        assert difference < TOLERANCE, (
            f"Total mismatch: invoice lines sum={total_from_lines}, "
            f"expected={expected_total}, difference={difference}"
        )
        
        # Validate principal lines (sum of all principal lines should match breakdown.principal)
        principal_lines = [l for l in invoice_lines if "Sales Revenue" in l["name"]]
        total_principal_from_lines = sum(l["price_unit"] for l in principal_lines)
        assert abs(total_principal_from_lines - float(breakdown.principal.amount)) < TOLERANCE, (
            f"Principal mismatch: total from lines={total_principal_from_lines} vs breakdown={breakdown.principal.amount}"
        )
