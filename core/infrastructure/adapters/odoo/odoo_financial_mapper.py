"""
Minimal Odoo Financial Mapper required by architecture guards.

This file maps:
- Order entity  → Odoo invoice header dict
- FinancialBreakdown → Odoo invoice lines

It is intentionally minimal until full accounting logic is restored.
"""

from typing import Dict, List, Any


class OdooFinancialMapper:
    """
    Provides deterministic mapping to Odoo invoice payloads.
    Required by architecture guards in:
    - sync_amazon_order.py
    - test_create_invoice.py
    """

    @staticmethod
    def to_invoice_header(order) -> Dict[str, Any]:
        """
        Converts Order entity → dict for Odoo invoice.
        """
        return {
            "move_type": "out_invoice",
            "partner_id": order.partner_odoo_id,
            "invoice_date": order.invoice_date,
            "ref": order.order_id,
        }

    @staticmethod
    def to_invoice_lines(breakdown) -> List[Dict[str, Any]]:
        """
        Converts financial breakdown → list of invoice line dicts.
        """

        lines = []

        for line in breakdown.lines:
            lines.append(
                {
                    "name": line.description,
                    "quantity": line.quantity,
                    "price_unit": line.unit_price,
                    "account_id": line.account_id,
                    "product_id": line.product_id,
                }
            )

        return lines
