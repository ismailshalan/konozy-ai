"""
Amazon Financial Events to Domain FinancialBreakdown mapper.

CRITICAL: This logic MUST produce IDENTICAL output to legacy system.
Any deviation in principal, fees, or net_proceeds = MISSION FAILURE.

Reference: docs/LEGACY_SYSTEM_ANALYSIS.md section "Extraction Algorithm"
"""
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime
import logging

from core.domain.value_objects import Money
from core.domain.value_objects import (
    FinancialLine,
    FinancialBreakdown,
    AmazonFeeType,
)
from .fee_config import AMAZON_FEE_MAPPINGS

logger = logging.getLogger(__name__)


class AmazonFeeMapper:
    """
    Maps Amazon Financial Events API response to domain FinancialBreakdown.
    
    This is the CORE financial extraction logic. Parity with legacy system
    is MANDATORY - any discrepancy indicates a bug.
    """
    
    @staticmethod
    def parse_financial_events(
        financial_events: Dict[str, Any],
        order_id: str
    ) -> FinancialBreakdown:
        """
        Extract financial breakdown from Amazon Financial Events API.
        
        This method replicates the EXACT logic from legacy system's
        AmazonFinancialSource extractor.
        
        Args:
            financial_events: FinancialEvents payload from Amazon API
            order_id: Amazon order ID (for logging)
        
        Returns:
            FinancialBreakdown with complete fee decomposition
        
        Raises:
            ValueError: If required data missing or invalid
        """
        principal = Decimal("0.00")
        financial_lines: List[FinancialLine] = []
        currency = "EGP"  # Default, will be overridden
        posted_date: Optional[datetime] = None
        
        logger.info(f"[FINANCES] Processing financial events for order {order_id}")
        
        # Extract from ShipmentEventList
        shipment_events = financial_events.get("ShipmentEventList", [])
        
        if not shipment_events:
            logger.warning(f"[FINANCES] No shipment events found for order {order_id}")
        
        for shipment in shipment_events:
            # Extract posted date (for invoice_date)
            if not posted_date and shipment.get("PostedDate"):
                posted_date = datetime.fromisoformat(
                    shipment["PostedDate"].replace("Z", "+00:00")
                )
                logger.debug(f"[FINANCES] Extracted PostedDate: {posted_date}")
            
            # Process each shipment item
            shipment_items = shipment.get("ShipmentItemList", [])
            logger.info(
                f"[FINANCES] Found {len(shipment_items)} shipment item(s) "
                f"for order {order_id}"
            )
            
            for item in shipment_items:
                sku = item.get("SellerSKU", "UNKNOWN")
                qty = int(item.get("QuantityShipped", 1))
                
                # ==============================================================
                # EXTRACT PRINCIPAL from ItemChargeList
                # ==============================================================
                for charge in item.get("ItemChargeList", []):
                    charge_type = charge["ChargeType"]
                    amount_data = charge["ChargeAmount"]
                    amount = Decimal(amount_data["CurrencyAmount"])
                    currency = amount_data["CurrencyCode"]
                    
                    if charge_type == "Principal":
                        principal += amount
                        logger.info(
                            f"[FINANCES] Extracted Principal item: "
                            f"SKU={sku}, qty={qty}, amount={amount} {currency}"
                        )
                    
                    elif charge_type == "ShippingCharge":
                        # Shipping is a charge (revenue)
                        mapping = AMAZON_FEE_MAPPINGS[AmazonFeeType.SHIPPING_CHARGE]
                        
                        financial_lines.append(FinancialLine(
                            line_type="charge",
                            fee_type=AmazonFeeType.SHIPPING_CHARGE,
                            amount=Money(amount=amount, currency=currency),
                            description="Amazon Shipping Charge",
                            sku=sku,
                            odoo_mapping=mapping
                        ))
                        
                        logger.info(
                            f"[FINANCES] Charge line: ShippingCharge -> "
                            f"Amazon Shipping Charge = {amount} {currency} "
                            f"(account={mapping.account_id}, "
                            f"analytic={mapping.analytic_account_id}, SKU={sku})"
                        )
                    
                    elif charge_type == "PaymentMethodFee":
                        # PaymentMethodFee is a charge (revenue) - same account as Principal
                        from .fee_config import PRINCIPAL_MAPPING
                        
                        financial_lines.append(FinancialLine(
                            line_type="charge",
                            fee_type=None,  # PaymentMethodFee is not in AmazonFeeType enum
                            amount=Money(amount=amount, currency=currency),
                            description="Amazon Payment Method Fee",
                            sku=sku,
                            odoo_mapping=PRINCIPAL_MAPPING
                        ))
                        
                        logger.info(
                            f"[FINANCES] Charge line: PaymentMethodFee -> "
                            f"Amazon Payment Method Fee = {amount} {currency} "
                            f"(account={PRINCIPAL_MAPPING.account_id}, SKU={sku})"
                        )
                
                # ==============================================================
                # EXTRACT FEES from ItemFeeList
                # ==============================================================
                for fee_item in item.get("ItemFeeList", []):
                    fee_type_str = fee_item["FeeType"]
                    fee_amount_data = fee_item["FeeAmount"]
                    fee_amount = Decimal(fee_amount_data["CurrencyAmount"])
                    currency = fee_amount_data["CurrencyCode"]
                    
                    # Map Amazon fee type to domain enum
                    fee_type = AmazonFeeMapper._map_fee_type(fee_type_str)
                    
                    if fee_type and fee_type in AMAZON_FEE_MAPPINGS:
                        mapping = AMAZON_FEE_MAPPINGS[fee_type]
                        
                        financial_lines.append(FinancialLine(
                            line_type="fee",
                            fee_type=fee_type,
                            amount=Money(amount=fee_amount, currency=currency),
                            description=f"Amazon {fee_type_str}",
                            sku=sku,
                            odoo_mapping=mapping
                        ))
                        
                        logger.info(
                            f"[FINANCES] Fee line: {fee_type_str} -> "
                            f"Amazon {fee_type_str} = {fee_amount} {currency} "
                            f"(account={mapping.account_id}, "
                            f"analytic={mapping.analytic_account_id}, SKU={sku})"
                        )
                    elif fee_type_str == "CODChargeback" or fee_type_str == "ShippingChargeback" or fee_type_str == "ShippingHB":
                        # Unknown fee types that should be included (expenses) - use same account as Commission/FBA
                        mapping = AMAZON_FEE_MAPPINGS[AmazonFeeType.COMMISSION]  # Use Commission account (1133)
                        
                        financial_lines.append(FinancialLine(
                            line_type="fee",
                            fee_type=None,  # Not in AmazonFeeType enum
                            amount=Money(amount=fee_amount, currency=currency),
                            description=f"Amazon {fee_type_str}",
                            sku=sku,
                            odoo_mapping=mapping
                        ))
                        
                        logger.info(
                            f"[FINANCES] Fee line: {fee_type_str} -> "
                            f"Amazon {fee_type_str} = {fee_amount} {currency} "
                            f"(account={mapping.account_id}, "
                            f"analytic={mapping.analytic_account_id}, SKU={sku})"
                        )
                    else:
                        # Skip zero-amount fees or unknown types (log warning only if non-zero)
                        if fee_amount != 0:
                            logger.warning(
                                f"[FINANCES] Unknown fee type: {fee_type_str} "
                                f"(amount={fee_amount}) for order {order_id}"
                            )
                
                # ==============================================================
                # EXTRACT PROMOTIONS from PromotionList
                # ==============================================================
                for promo in item.get("PromotionList", []):
                    promo_amount_data = promo["PromotionAmount"]
                    promo_amount = Decimal(promo_amount_data["CurrencyAmount"])
                    currency = promo_amount_data["CurrencyCode"]
                    
                    mapping = AMAZON_FEE_MAPPINGS[AmazonFeeType.PROMO_REBATE]
                    
                    financial_lines.append(FinancialLine(
                        line_type="promo",
                        fee_type=AmazonFeeType.PROMO_REBATE,
                        amount=Money(amount=promo_amount, currency=currency),
                        description="Amazon Promotion Rebate",
                        sku=sku,
                        odoo_mapping=mapping
                    ))
                    
                    logger.info(
                        f"[FINANCES] Promo line: PROMO_REBATE -> "
                        f"Amazon Promotion Rebate = {promo_amount} {currency} "
                        f"(account={mapping.account_id}, "
                        f"analytic={mapping.analytic_account_id})"
                    )
        
        # ==================================================================
        # CALCULATE NET PROCEEDS
        # ==================================================================
        total_lines = sum(line.amount.amount for line in financial_lines)
        net_proceeds = principal + total_lines
        
        # Summary logging (matches legacy format)
        total_charges = sum(
            line.amount.amount 
            for line in financial_lines 
            if line.line_type == "charge"
        )
        total_fees = sum(
            line.amount.amount 
            for line in financial_lines 
            if line.line_type == "fee"
        )
        total_promos = sum(
            line.amount.amount 
            for line in financial_lines 
            if line.line_type == "promo"
        )
        
        logger.info(
            f"[FINANCES] Order {order_id} summary: "
            f"Charges={total_charges:.2f}, Fees={total_fees:.2f}, "
            f"Promos={total_promos:.2f}"
        )
        logger.info(
            f"[FINANCES] Total Principal extracted: {principal} {currency}"
        )
        logger.info(
            f"[FINANCES] Built {len(financial_lines)} financial lines "
            f"for order {order_id}"
        )
        
        return FinancialBreakdown(
            principal=Money(amount=principal, currency=currency),
            financial_lines=financial_lines,
            net_proceeds=Money(amount=net_proceeds, currency=currency),
            posted_date=posted_date
        )
    
    @staticmethod
    def _map_fee_type(amazon_fee_type: str) -> Optional[AmazonFeeType]:
        """
        Map Amazon fee type string to domain enum.
        
        Args:
            amazon_fee_type: Fee type from Amazon API
        
        Returns:
            AmazonFeeType enum or None if unknown
        """
        mapping = {
            "FBAPerUnitFulfillmentFee": AmazonFeeType.FBA_FULFILLMENT,
            "Commission": AmazonFeeType.COMMISSION,
            "RefundCommission": AmazonFeeType.REFUND_COMMISSION,
            "ShippingCharge": AmazonFeeType.SHIPPING_CHARGE,
            "StorageFee": AmazonFeeType.STORAGE_FEE,
            # Add more as needed
        }
        return mapping.get(amazon_fee_type)
    
    @staticmethod
    def extract_sku_to_principal(
        financial_events: Dict[str, Any]
    ) -> Dict[str, Decimal]:
        """
        Extract SKU-level principal breakdown for multi-item orders.
        
        For orders with multiple different products, this extracts
        how much principal revenue belongs to each SKU.
        
        Args:
            financial_events: Amazon Financial Events API response
        
        Returns:
            Dictionary mapping SKU to principal amount
            Example: {
                "JR-ZS283": Decimal("198.83"),
                "jr_PBF17 __Black": Decimal("790.0")
            }
        
        Example:
            >>> events = {
            ...     "ShipmentEventList": [{
            ...         "ShipmentItemList": [
            ...             {
            ...                 "SellerSKU": "SKU-A",
            ...                 "ItemChargeList": [{
            ...                     "ChargeType": "Principal",
            ...                     "ChargeAmount": {"CurrencyAmount": "100.00"}
            ...                 }]
            ...             },
            ...             {
            ...                 "SellerSKU": "SKU-B",
            ...                 "ItemChargeList": [{
            ...                     "ChargeType": "Principal",
            ...                     "ChargeAmount": {"CurrencyAmount": "200.00"}
            ...                 }]
            ...             }
            ...         ]
            ...     }]
            ... }
            >>> extract_sku_to_principal(events)
            {'SKU-A': Decimal('100.00'), 'SKU-B': Decimal('200.00')}
        """
        sku_to_principal: Dict[str, Decimal] = {}
        
        shipment_events = financial_events.get("ShipmentEventList", [])
        
        for shipment in shipment_events:
            shipment_items = shipment.get("ShipmentItemList", [])
            
            for item in shipment_items:
                sku = item.get("SellerSKU", "UNKNOWN")
                
                # Extract principal charges for this SKU
                for charge in item.get("ItemChargeList", []):
                    if charge["ChargeType"] == "Principal":
                        amount_data = charge["ChargeAmount"]
                        amount = Decimal(str(amount_data["CurrencyAmount"]))
                        
                        # Accumulate if SKU appears multiple times
                        # (e.g., same SKU in multiple shipments)
                        if sku in sku_to_principal:
                            sku_to_principal[sku] += amount
                        else:
                            sku_to_principal[sku] = amount
                        
                        logger.debug(
                            f"[SKU_PRINCIPAL] Extracted principal for SKU {sku}: "
                            f"{amount} (total so far: {sku_to_principal[sku]})"
                        )
        
        logger.info(
            f"[SKU_PRINCIPAL] Extracted principal for {len(sku_to_principal)} SKU(s): "
            f"{dict(sku_to_principal)}"
        )
        
        return sku_to_principal
    
    @staticmethod
    def calculate_sku_breakdown(
        financial_events: Dict[str, Any],
        order_id: str,
        sku: str
    ) -> Dict[str, Decimal]:
        """
        Calculate financial breakdown for a specific SKU in multi-item order.
        
        This method extracts Principal, Fees, Charges, and Promos for a specific SKU,
        matching the legacy system's per-SKU calculation logic.
        
        Args:
            financial_events: Amazon Financial Events API response
            order_id: Amazon order ID (for logging)
            sku: SKU to calculate breakdown for
        
        Returns:
            Dictionary with:
            - principal: Principal amount for this SKU
            - charges: Total charges (ShippingCharge + PaymentMethodFee) for this SKU
            - fees: Total fees for this SKU
            - promos: Total promotions for this SKU
            - total_sales: Principal + Charges (matches legacy إجمالي_المبيعات)
            - net_proceeds: Total Sales + Fees + Promos (matches legacy صافي_المبلغ)
        """
        principal = Decimal("0")
        charges = Decimal("0")
        fees = Decimal("0")
        promos = Decimal("0")
        
        shipment_events = financial_events.get("ShipmentEventList", [])
        
        for shipment in shipment_events:
            shipment_items = shipment.get("ShipmentItemList", [])
            
            for item in shipment_items:
                item_sku = item.get("SellerSKU", "UNKNOWN")
                
                if item_sku != sku:
                    continue  # Skip items not matching target SKU
                
                # Extract Principal and Charges
                for charge in item.get("ItemChargeList", []):
                    charge_type = charge["ChargeType"]
                    amount_data = charge["ChargeAmount"]
                    amount = Decimal(amount_data["CurrencyAmount"])
                    
                    if charge_type == "Principal":
                        principal += amount
                    elif charge_type in ["ShippingCharge", "PaymentMethodFee"]:
                        charges += amount
                
                # Extract Item Fees
                for fee_item in item.get("ItemFeeList", []):
                    fee_amount_data = fee_item["FeeAmount"]
                    fee_amount = Decimal(fee_amount_data["CurrencyAmount"])
                    fees += fee_amount
                
                # Extract Item Promotions
                for promo in item.get("PromotionList", []):
                    promo_amount_data = promo["PromotionAmount"]
                    promo_amount = Decimal(promo_amount_data["CurrencyAmount"])
                    promos += promo_amount
        
        # Calculate totals (matching legacy system)
        total_sales = principal + charges
        net_proceeds = total_sales + fees + promos
        
        logger.debug(
            f"[SKU_BREAKDOWN] SKU {sku} in order {order_id}: "
            f"Principal={principal}, Charges={charges}, Fees={fees}, "
            f"Promos={promos}, TotalSales={total_sales}, Net={net_proceeds}"
        )
        
        return {
            "principal": principal,
            "charges": charges,
            "fees": fees,
            "promos": promos,
            "total_sales": total_sales,
            "net_proceeds": net_proceeds,
        }