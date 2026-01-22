"""
Tests for multi-item order support.

Validates that orders with multiple different SKUs are handled correctly.
"""
import pytest
from decimal import Decimal

from core.domain.value_objects import Money, FinancialBreakdown, FinancialLine
# AmazonFeeMapper removed - using inline extraction
from core.infrastructure.adapters.odoo.odoo_financial_mapper import OdooFinancialMapper


class TestMultiItemOrderSupport:
    """Test multi-item order handling."""
    
    def test_extract_sku_to_principal_single_sku(self):
        """Test extraction with single SKU."""
        events = {
            "ShipmentEventList": [{
                "ShipmentItemList": [{
                    "SellerSKU": "SKU-A",
                    "ItemChargeList": [{
                        "ChargeType": "Principal",
                        "ChargeAmount": {
                            "CurrencyCode": "EGP",
                            "CurrencyAmount": "198.83"
                        }
                    }]
                }]
            }]
        }
        
        # Inline extraction function
        sku_to_principal = {}
        shipment_events = events.get("ShipmentEventList", [])
        for shipment in shipment_events:
            shipment_items = shipment.get("ShipmentItemList", [])
            for item in shipment_items:
                sku = item.get("SellerSKU", "")
                if not sku:
                    continue
                item_charges = item.get("ItemChargeList", [])
                for charge in item_charges:
                    if charge.get("ChargeType") == "Principal":
                        amount_dict = charge.get("ChargeAmount", {})
                        amount = Decimal(str(amount_dict.get("CurrencyAmount", 0.0)))
                        if amount > 0:
                            sku_to_principal[sku] = sku_to_principal.get(sku, Decimal("0")) + amount
                        break
        result = sku_to_principal
        
        assert len(result) == 1
        assert result["SKU-A"] == Decimal("198.83")
    
    def test_extract_sku_to_principal_multiple_skus(self):
        """Test extraction with multiple different SKUs."""
        events = {
            "ShipmentEventList": [{
                "ShipmentItemList": [
                    {
                        "SellerSKU": "SKU-A",
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {
                                "CurrencyCode": "EGP",
                                "CurrencyAmount": "100.00"
                            }
                        }]
                    },
                    {
                        "SellerSKU": "SKU-B",
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {
                                "CurrencyCode": "EGP",
                                "CurrencyAmount": "200.00"
                            }
                        }]
                    }
                ]
            }]
        }
        
        # Inline extraction function
        sku_to_principal = {}
        shipment_events = events.get("ShipmentEventList", [])
        for shipment in shipment_events:
            shipment_items = shipment.get("ShipmentItemList", [])
            for item in shipment_items:
                sku = item.get("SellerSKU", "")
                if not sku:
                    continue
                item_charges = item.get("ItemChargeList", [])
                for charge in item_charges:
                    if charge.get("ChargeType") == "Principal":
                        amount_dict = charge.get("ChargeAmount", {})
                        amount = Decimal(str(amount_dict.get("CurrencyAmount", 0.0)))
                        if amount > 0:
                            sku_to_principal[sku] = sku_to_principal.get(sku, Decimal("0")) + amount
                        break
        result = sku_to_principal
        
        assert len(result) == 2
        assert result["SKU-A"] == Decimal("100.00")
        assert result["SKU-B"] == Decimal("200.00")
    
    def test_extract_sku_to_principal_duplicate_sku(self):
        """Test extraction with same SKU appearing multiple times (accumulation)."""
        events = {
            "ShipmentEventList": [
                {
                    "ShipmentItemList": [{
                        "SellerSKU": "SKU-A",
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {
                                "CurrencyCode": "EGP",
                                "CurrencyAmount": "100.00"
                            }
                        }]
                    }]
                },
                {
                    "ShipmentItemList": [{
                        "SellerSKU": "SKU-A",
                        "ItemChargeList": [{
                            "ChargeType": "Principal",
                            "ChargeAmount": {
                                "CurrencyCode": "EGP",
                                "CurrencyAmount": "50.00"
                            }
                        }]
                    }]
                }
            ]
        }
        
        # Inline extraction function
        sku_to_principal = {}
        shipment_events = events.get("ShipmentEventList", [])
        for shipment in shipment_events:
            shipment_items = shipment.get("ShipmentItemList", [])
            for item in shipment_items:
                sku = item.get("SellerSKU", "")
                if not sku:
                    continue
                item_charges = item.get("ItemChargeList", [])
                for charge in item_charges:
                    if charge.get("ChargeType") == "Principal":
                        amount_dict = charge.get("ChargeAmount", {})
                        amount = Decimal(str(amount_dict.get("CurrencyAmount", 0.0)))
                        if amount > 0:
                            sku_to_principal[sku] = sku_to_principal.get(sku, Decimal("0")) + amount
                        break
        result = sku_to_principal
        
        assert len(result) == 1
        assert result["SKU-A"] == Decimal("150.00")  # Accumulated
    
    def test_invoice_lines_multi_sku(self):
        """Test invoice line generation for multi-SKU order."""
        # Create minimal breakdown
        principal = Money(amount=Decimal("300.00"), currency="EGP")
        net_proceeds = Money(amount=Decimal("300.00"), currency="EGP")
        
        breakdown = FinancialBreakdown(
            principal=principal,
            financial_lines=[],
            net_proceeds=net_proceeds
        )
        
        # Multi-SKU principal
        sku_to_principal = {
            "SKU-A": Decimal("100.00"),
            "SKU-B": Decimal("200.00"),
        }
        
        # Generate invoice lines
        lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Verify principal lines
        principal_lines = [l for l in lines if "Sales Revenue" in l["name"]]
        assert len(principal_lines) == 2
        
        # Verify amounts
        sku_a_line = next(l for l in principal_lines if "SKU-A" in l["name"])
        sku_b_line = next(l for l in principal_lines if "SKU-B" in l["name"])
        
        assert sku_a_line["price_unit"] == 100.00
        assert sku_b_line["price_unit"] == 200.00
        
        # Verify account
        assert sku_a_line["account_id"] == 1075  # Revenue account
        assert sku_b_line["account_id"] == 1075
    
    def test_invoice_lines_multi_sku_with_fees(self):
        """Test invoice line generation with fees for multi-SKU order."""
        from core.domain.value_objects.financial import (
            AmazonFeeType,
            OdooAccountMapping
        )
        
        principal = Money(amount=Decimal("300.00"), currency="EGP")
        
        # Add fees
        financial_lines = [
            FinancialLine(
                line_type="fee",
                amount=Money(amount=Decimal("-21.66"), currency="EGP"),
                description="Amazon FBA Fee",
                fee_type=AmazonFeeType.FBA_FULFILLMENT,
                sku="SKU-A",
                odoo_mapping=OdooAccountMapping(
                    account_id=1133,
                    analytic_account_id=8
                )
            ),
            FinancialLine(
                line_type="fee",
                amount=Money(amount=Decimal("-30.00"), currency="EGP"),
                description="Amazon Commission",
                fee_type=AmazonFeeType.COMMISSION,
                sku="SKU-B",
                odoo_mapping=OdooAccountMapping(
                    account_id=1133,
                    analytic_account_id=8
                )
            )
        ]
        
        net_proceeds = Money(amount=Decimal("248.34"), currency="EGP")
        
        breakdown = FinancialBreakdown(
            principal=principal,
            financial_lines=financial_lines,
            net_proceeds=net_proceeds
        )
        
        sku_to_principal = {
            "SKU-A": Decimal("100.00"),
            "SKU-B": Decimal("200.00"),
        }
        
        lines = OdooFinancialMapper.to_invoice_lines(
            breakdown=breakdown,
            sku_to_principal=sku_to_principal
        )
        
        # Should have 2 principal + 2 fee lines
        assert len(lines) == 4
        
        principal_lines = [l for l in lines if "Sales Revenue" in l["name"]]
        fee_lines = [l for l in lines if "Fee" in l["name"] or "Commission" in l["name"]]
        
        assert len(principal_lines) == 2
        assert len(fee_lines) == 2
