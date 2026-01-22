"""
Amazon Financial Source

Domain layer for Amazon financial data processing.
Owns PostedDate parsing logic and enforces "PostedDate is the only source of truth".
Processes raw financial events from Amazon SP-API into normalized financial lines.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from konozy_odoo_sdk.core.logger import get_logger

logger = get_logger("AmazonFinancialSource")


def parse_posted_date(order_date: str) -> datetime:
    """
    Strict parser for Amazon PostedDate (ISO8601 Z format).
    
    ARCHITECTURAL RULE: Amazon PostedDate is the ONLY source of truth for all dates.
    This function NEVER fallbacks, guesses, or defaults.
    
    Args:
        order_date: ISO8601 Z format datetime string (e.g., "2025-09-01T12:34:56Z")
    
    Returns:
        Timezone-aware UTC datetime object.
    
    Raises:
        ValueError: If order_date is None, empty, or invalid format.
                    Error message includes "ARCHITECTURE VIOLATION" prefix.
    """
    if not order_date:
        raise ValueError(
            "ARCHITECTURE VIOLATION: order_date (Amazon PostedDate) is required. No fallback allowed."
        )
    
    if not isinstance(order_date, str):
        raise ValueError(
            f"ARCHITECTURE VIOLATION: Invalid order_date type: {type(order_date)}. "
            f"Expected string in ISO8601 Z format (e.g., '2025-09-01T12:34:56Z')."
        )
    
    order_date = order_date.strip()
    
    if not order_date:
        raise ValueError(
            "ARCHITECTURE VIOLATION: order_date (Amazon PostedDate) is required. No fallback allowed."
        )
    
    try:
        # Parse ISO8601 Z format: %Y-%m-%dT%H:%M:%SZ
        if not order_date.endswith("Z"):
            raise ValueError(
                f"ARCHITECTURE VIOLATION: Invalid order_date format: '{order_date}'. "
                f"Expected ISO8601 Z format (e.g., '2025-09-01T12:34:56Z')."
            )
        
        # Replace Z with +00:00 for timezone-aware parsing
        order_date_iso = order_date.replace("Z", "+00:00")
        order_dt = datetime.fromisoformat(order_date_iso)
        
        # Ensure it's UTC timezone-aware
        if order_dt.tzinfo is None:
            order_dt = order_dt.replace(tzinfo=timezone.utc)
        elif order_dt.tzinfo != timezone.utc:
            # Convert to UTC if timezone-aware but not UTC
            order_dt = order_dt.astimezone(timezone.utc)
        
        return order_dt
        
    except ValueError as e:
        # Re-raise with architecture violation prefix if not already present
        error_msg = str(e)
        if "ARCHITECTURE VIOLATION" not in error_msg:
            raise ValueError(
                f"ARCHITECTURE VIOLATION: Invalid order_date format: '{order_date}'. "
                f"Expected ISO8601 Z format (e.g., '2025-09-01T12:34:56Z'). Original error: {error_msg}"
            ) from e
        raise
    except Exception as e:
        raise ValueError(
            f"ARCHITECTURE VIOLATION: Failed to parse order_date: '{order_date}'. "
            f"Expected ISO8601 Z format (e.g., '2025-09-01T12:34:56Z'). Error: {e}"
        ) from e


class AmazonFinancialSource:
    """
    Amazon Financial Source - domain layer for Amazon financial data processing.
    
    Owns PostedDate parsing logic and enforces "PostedDate is the only source of truth".
    Processes raw financial events from Amazon SP-API into normalized financial lines.
    
    This class contains domain logic for:
    - PostedDate parsing and validation
    - SKU resolution from financial events
    - Fee/charge mapping to accounting codes
    - Financial line building from raw Amazon events
    """
    
    def __init__(self, amazon_api: Any):
        """
        Initialize Amazon Financial Source.
        
        Args:
            amazon_api: AmazonAPI client instance (for SKU resolution via Orders API)
        """
        self.amazon_api = amazon_api
    
    def _normalize_amazon_order_id(self, amazon_order_id: str) -> str:
        """
        Normalize Amazon order ID by removing prefixes and whitespace.
        
        Args:
            amazon_order_id: Amazon order ID (may include "AMZ-", "S01-", "S02-", "S03-" prefixes)
        
        Returns:
            Cleaned order ID string in Amazon native format (e.g., "402-6202063-8451542").
            Returns empty string if input is None or empty.
        """
        if not amazon_order_id:
            return ""
        
        raw = amazon_order_id
        clean = amazon_order_id.strip()
        
        # Remove "AMZ-" prefix if present
        if clean.startswith("AMZ-"):
            clean = clean[4:]
        
        # Remove S01-, S02-, S03- prefixes if present
        # Example: "S02-5369777-2251569" → "5369777-2251569"
        if clean.startswith(("S01-", "S02-", "S03-")):
            clean = clean.split("-", 1)[1]
        
        logger.debug(f"[FINANCES] Normalized ID from '{raw}' → '{clean}'")
        return clean
    
    def _resolve_sku_for_financial_event(
        self, 
        financial_event: Dict[str, Any], 
        order_id: str
    ) -> Optional[str]:
        """
        Resolve SKU for a financial event using the following logic:
        1. If Financial Event contains SKU → use it
        2. Else: Fetch order items via Orders API using order_id
        3. If exactly ONE SKU exists → assign it
        4. If multiple SKUs → do NOT assign SKU (return None)
        5. Never fabricate or guess SKU
        
        Args:
            financial_event: Financial event dictionary from Amazon
            order_id: Amazon order ID (normalized)
        
        Returns:
            SKU string if resolved, None if not resolvable or multiple SKUs found.
        """
        # Step 1: Check if SKU exists directly in financial event
        sku = financial_event.get("SellerSKU") or financial_event.get("sku")
        if sku:
            logger.info(f"[SKU_RESOLUTION] SKU found directly in financial event: {sku} (order_id={order_id})")
            return sku
        
        # Step 2: Fetch order items via Orders API
        logger.info(f"[SKU_RESOLUTION] No SKU in financial event, fetching order items for order_id={order_id}")
        order_items = self.amazon_api.fetch_order_items(order_id)
        
        if not order_items:
            logger.warning(f"[SKU_RESOLUTION] No order items found for order_id={order_id}, SKU cannot be resolved")
            return None
        
        # Extract unique SKUs
        skus = list(set(item.get("sku", "") for item in order_items if item.get("sku")))
        
        if len(skus) == 0:
            logger.warning(f"[SKU_RESOLUTION] No SKUs found in order items for order_id={order_id}")
            return None
        elif len(skus) == 1:
            logger.info(f"[SKU_RESOLUTION] Exactly one SKU found via Orders API: {skus[0]} (order_id={order_id})")
            return skus[0]
        else:
            logger.warning(
                f"[SKU_RESOLUTION] Multiple SKUs found ({len(skus)}): {', '.join(skus)} "
                f"(order_id={order_id}). SKU will NOT be assigned per requirements."
            )
            return None
    
    def _map_fee_to_line(
        self,
        fee_type: str,
        raw_amount: float,
        accounting_cfg: Any,
        analytics_cfg: Any,
        currency_code: str = "EGP"
    ) -> Optional[Dict[str, Any]]:
        """
        Map a fee type and amount to a financial line configuration.
        
        Args:
            fee_type: Fee type string from Amazon
            raw_amount: Raw amount from Amazon (preserves sign: negative for fees)
            accounting_cfg: AccountingConfig instance
            analytics_cfg: AnalyticsConfig instance
            currency_code: Currency code from Amazon (default: EGP)
        
        Returns:
            Dictionary with line configuration or None if invalid.
        """
        if raw_amount == 0:
            return None
        
        fee_type_upper = fee_type.upper()
        # Preserve exact sign from Amazon (Amazon already provides correct sign)
        amount = round(raw_amount, 2)
        
        # Map fee type to line configuration
        if "COMMISSION" in fee_type_upper or "REFERRAL" in fee_type_upper:
            return {
                "code": "COMMISSION",
                "name": "Amazon Commission",
                "amount": amount,  # Preserve sign from Amazon
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_COMMISSIONS_ID,
                "analytic_id": analytics_cfg.AMAZON_COMMISSIONS_ANALYTIC_ID,
            }
        elif any(x in fee_type_upper for x in [
            "FBA_PER_UNIT_FULFILLMENT", "FBA_PICK_AND_PACK", 
            "FBA_PER_ORDER_FULFILLMENT", "FBA_PICK_PACK",
            "FBA_PER_UNIT_FULFILLMENT_FEE", "FBA_PER_ORDER_FULFILLMENT_FEE"
        ]):
            return {
                "code": "FBA_PICK_AND_PACK",
                "name": "Amazon FBA Pick & Pack Fee",
                "amount": amount,  # Preserve sign from Amazon
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_FBA_PICK_PACK_FEE_ID,
                "analytic_id": analytics_cfg.ANALYTIC_AMAZON_SHIPPING_COST_ID,
            }
        elif "COD" in fee_type_upper:
            return {
                "code": "COD_FEE",
                "name": "Amazon COD Fee",
                "amount": amount,  # Preserve sign from Amazon
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_COD_FEE_ID,
                "analytic_id": analytics_cfg.ANALYTIC_AMAZON_SHIPPING_COST_ID,
            }
        elif "SHIPPING" in fee_type_upper:
            if "CHARGEBACK" in fee_type_upper or "DISCOUNT" in fee_type_upper:
                return {
                    "code": "SHIPPING_CHARGEBACK",
                    "name": "Amazon Shipping Chargeback",
                    "amount": amount,  # Preserve sign from Amazon
                    "currency": currency_code,
                    "account_id": accounting_cfg.AMAZON_SALES_ID,
                    "analytic_id": analytics_cfg.ANALYTIC_AMAZON_SHIPPING_COST_ID,
                }
            else:
                # ShippingCharge (from fees) - should be negative
                return {
                    "code": "SHIPPING_FEE",
                    "name": "Amazon Shipping Fee",
                    "amount": amount,  # Preserve sign from Amazon
                    "currency": currency_code,
                    "account_id": accounting_cfg.AMAZON_SALES_ID,
                    "analytic_id": analytics_cfg.ANALYTIC_AMAZON_SHIPPING_COST_ID,
                }
        else:
            # Other fees (VariableClosingFee, etc.)
            return {
                "code": "OTHER_FEE",
                "name": f"Amazon {fee_type}",
                "amount": amount,  # Preserve sign from Amazon
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_COMMISSIONS_ID,
                "analytic_id": analytics_cfg.AMAZON_COMMISSIONS_ANALYTIC_ID,
            }
    
    def _map_charge_to_line(
        self,
        charge_type: str,
        raw_amount: float,
        accounting_cfg: Any,
        analytics_cfg: Any,
        currency_code: str = "EGP"
    ) -> Optional[Dict[str, Any]]:
        """
        Map a charge type and amount to a financial line configuration.
        
        Args:
            charge_type: Charge type string from Amazon (ShippingCharge, PaymentMethodFee, Tax, etc.)
            raw_amount: Raw amount from Amazon (preserves sign)
            accounting_cfg: AccountingConfig instance
            analytics_cfg: AnalyticsConfig instance
            currency_code: Currency code from Amazon (default: EGP)
        
        Returns:
            Dictionary with line configuration or None if invalid.
            Note: Principal charges are skipped (handled separately to override product price).
        """
        if raw_amount == 0:
            return None
        
        charge_type_upper = charge_type.upper()
        # Preserve exact sign from Amazon
        amount = round(raw_amount, 2)
        
        # Map charge type to line configuration
        if "SHIPPING" in charge_type_upper:
            if "TAX" in charge_type_upper:
                # ShippingTax - usually 0 in EG, but include if present
                return {
                    "code": "SHIPPING_TAX",
                    "name": "Amazon Shipping Tax",
                    "amount": amount,
                    "currency": currency_code,
                    "account_id": accounting_cfg.AMAZON_SALES_ID,
                    "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
                }
            else:
                # ShippingCharge - positive revenue
                return {
                    "code": "SHIPPING_CHARGE",
                    "name": "Amazon Shipping Charge",
                    "amount": amount,  # Positive revenue
                    "currency": currency_code,
                    "account_id": accounting_cfg.AMAZON_SALES_ID,
                    "analytic_id": analytics_cfg.ANALYTIC_AMAZON_SHIPPING_COST_ID,
                }
        elif "PAYMENT" in charge_type_upper or "METHOD" in charge_type_upper:
            # PaymentMethodFee - positive revenue (COD fee charged to customer)
            return {
                "code": "PAYMENT_METHOD_FEE",
                "name": "Amazon Payment Method Fee",
                "amount": amount,  # Positive revenue
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_SALES_ID,
                "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
            }
        elif "TAX" in charge_type_upper:
            # Tax charges (usually 0 in EG marketplace)
            return {
                "code": "TAX",
                "name": "Amazon Tax",
                "amount": amount,
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_SALES_ID,
                "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
            }
        elif "GIFT" in charge_type_upper:
            # GiftWrap charges (usually 0)
            return {
                "code": "GIFT_WRAP",
                "name": "Amazon Gift Wrap",
                "amount": amount,
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_SALES_ID,
                "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
            }
        else:
            # Other charges - default to sales account
            return {
                "code": "OTHER_CHARGE",
                "name": f"Amazon {charge_type}",
                "amount": amount,
                "currency": currency_code,
                "account_id": accounting_cfg.AMAZON_SALES_ID,
                "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
            }
    
    def build_financial_lines_for_order(
        self, 
        amazon_order_id: str, 
        raw_financial_events: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Build financial lines for a specific order from raw financial events.
        
        Filters events where AmazonOrderId matches the order, then creates
        one invoice line per financial event (no aggregation).
        Separates reimbursements from regular financial events.
        
        ARCHITECTURAL RULE: PostedDate from Amazon financial events is the ONLY source of truth.
        
        Args:
            amazon_order_id: Amazon order ID (may include "AMZ-" prefix)
            raw_financial_events: List of FinancialEvents dictionaries from AmazonAPI.fetch_financial_events_by_date()
        
        Returns:
            Tuple of (financial_lines, reimbursements):
            - financial_lines: List of dictionaries with structure:
                [
                    {
                        "code": str,          # e.g. REFERRAL_FEE, FBA_PICK_AND_PACK
                        "name": str,          # Human readable name
                        "amount": float,      # Signed amount (negative for fees)
                        "account_id": int,
                        "analytic_id": int,
                        "sku": Optional[str]  # SKU if resolved
                    },
                    ...
                ]
            - reimbursements: List of reimbursement dictionaries:
                [
                    {
                        "event_type": str,    # e.g. "FBA_INVENTORY_REIMBURSEMENT"
                        "amount": float,      # Reimbursement amount (positive)
                        "currency": str,
                        "order_id": str,
                        "sku": Optional[str], # SKU if resolved
                        "posted_date": str
                    },
                    ...
                ]
            
            Empty lists if no events found for this order. Never raises exceptions.
        """
        try:
            # Import config classes for account/analytic IDs
            # Use factory for lazy-loaded configs
            from konozy_sdk.config.factory import get_factory
            factory = get_factory()
            accounting_cfg = factory.get_accounting()
            analytics_cfg = factory.get_analytics()
            
            # Normalize order ID for matching
            clean_id = self._normalize_amazon_order_id(amazon_order_id)
            
            if not clean_id:
                logger.debug(f"[FINANCES] Invalid order ID: {amazon_order_id}")
                return [], []
            
            if not raw_financial_events:
                logger.debug(f"[FINANCES] No raw events provided for {clean_id}")
                return [], []
            
            financial_lines = []
            reimbursements = []  # Track FBA Inventory Reimbursements separately
            principal_amounts = []  # Track Principal amounts per item (for product price override)
            principal_items = []  # Track Principal items with SKU, qty, principal_amount, currency (DO NOT aggregate)
            posted_dates = []  # Track PostedDate from Amazon financial events (for invoice date extraction)
            
            # Process each FinancialEvents page
            for financial_events_page in raw_financial_events:
                # ============================================================
                # Parse FBA Inventory Reimbursement Events (separate handling)
                # ============================================================
                fba_reimbursement_events = financial_events_page.get("FbaInventoryReimbursementEventList", [])
                for reimbursement_event in fba_reimbursement_events:
                    # Check if this reimbursement is for our order
                    reimbursement_order_id = reimbursement_event.get("AmazonOrderId", "")
                    if reimbursement_order_id and reimbursement_order_id != clean_id:
                        continue
                    
                    # Extract reimbursement details
                    reimbursements_list = reimbursement_event.get("Reimbursements", [])
                    for reimbursement in reimbursements_list:
                        amount_dict = reimbursement.get("ReimbursementAmount", {})
                        amount = float(amount_dict.get("CurrencyAmount", 0.0))
                        currency = amount_dict.get("CurrencyCode", "EGP")
                        posted_date = reimbursement_event.get("PostedDate", "")
                        
                        if amount == 0:
                            continue
                        
                        # Resolve SKU for reimbursement
                        sku = None
                        if reimbursement_order_id:
                            sku = self._resolve_sku_for_financial_event(reimbursement, reimbursement_order_id)
                        
                        reimbursement_data = {
                            "event_type": "FBA_INVENTORY_REIMBURSEMENT",
                            "amount": round(amount, 2),
                            "currency": currency,
                            "order_id": reimbursement_order_id or clean_id,
                            "sku": sku,
                            "posted_date": posted_date,
                            "sku_source": "direct" if reimbursement.get("SellerSKU") or reimbursement.get("sku") else ("order_lookup" if sku else "none")
                        }
                        reimbursements.append(reimbursement_data)
                        
                        logger.info(
                            f"[FINANCES][REIMBURSEMENT] FBA Inventory Reimbursement detected: "
                            f"order_id={reimbursement_data['order_id']}, amount={amount} {currency}, "
                            f"SKU={sku or 'NONE'}, SKU_source={reimbursement_data['sku_source']}"
                        )
                
                # ============================================================
                # Parse ShipmentEventList (regular financial events)
                # ============================================================
                shipment_events = financial_events_page.get("ShipmentEventList", [])
                for shipment in shipment_events:
                    shipment_order_id = shipment.get("AmazonOrderId", "")
                    if shipment_order_id != clean_id:
                        continue
                    
                    # Extract PostedDate from shipment (for invoice date extraction)
                    shipment_posted_date = shipment.get("PostedDate")
                    if shipment_posted_date:
                        posted_dates.append(shipment_posted_date)
                    
                    # Process ItemFeeList, ItemChargeList, and PromotionList
                    shipment_items = shipment.get("ShipmentItemList", [])
                    logger.info(f"[FINANCES] Found {len(shipment_items)} shipment item(s) for order {clean_id}")
                    
                    charges_total = 0.0
                    fees_total = 0.0
                    promos_total = 0.0
                    
                    for item in shipment_items:
                        # Extract PostedDate from item (fallback if shipment PostedDate not available)
                        item_posted_date = item.get("PostedDate")
                        if item_posted_date:
                            posted_dates.append(item_posted_date)
                        
                        # Extract SKU and quantity from ShipmentItemList (Amazon Finances is the source of truth)
                        # Use SKU resolution logic: if SKU in event use it, else try to resolve via Orders API
                        sku = item.get("SellerSKU", "")
                        if not sku:
                            # Try to resolve SKU via Orders API if not present in financial event
                            sku = self._resolve_sku_for_financial_event(item, clean_id)
                            if sku:
                                logger.info(f"[FINANCES] SKU resolved via Orders API: {sku} for order {clean_id}")
                            else:
                                logger.warning(f"[FINANCES] SKU could not be resolved for order {clean_id} - item will be processed without SKU")
                        
                        qty = int(item.get("QuantityShipped", 1))
                        
                        # Extract Principal amount and currency for this item
                        item_principal_amount = 0.0
                        item_principal_currency = "EGP"
                        item_charges = item.get("ItemChargeList", [])
                        for charge in item_charges:
                            if charge.get("ChargeType") == "Principal":
                                amount_dict = charge.get("ChargeAmount", {})
                                item_principal_amount = float(amount_dict.get("CurrencyAmount", 0.0))
                                item_principal_currency = amount_dict.get("CurrencyCode", "EGP")
                                break
                        
                        # Store principal item with SKU (DO NOT aggregate - each ShipmentItem remains distinct)
                        if sku and item_principal_amount != 0:
                            principal_items.append({
                                "sku": sku,
                                "qty": qty,
                                "principal_amount": round(item_principal_amount, 2),
                                "currency": item_principal_currency,
                            })
                            logger.info(f"[FINANCES] Extracted Principal item: SKU={sku}, qty={qty}, amount={item_principal_amount} {item_principal_currency}")
                        
                        # ItemFeeList - Process all fees (Commission, FBA fees, COD, etc.)
                        item_fees = item.get("ItemFeeList", [])
                        for fee in item_fees:
                            fee_type = fee.get("FeeType", "")
                            amount_dict = fee.get("FeeAmount", {})
                            # Use CurrencyAmount (Amazon EG marketplace uses this field)
                            raw_amount = float(amount_dict.get("CurrencyAmount", 0.0))
                            currency_code = amount_dict.get("CurrencyCode", "EGP")
                            
                            if fee_type and raw_amount != 0:
                                line = self._map_fee_to_line(
                                    fee_type, raw_amount, accounting_cfg, analytics_cfg, currency_code
                                )
                                if line:
                                    # Add SKU to line if resolved
                                    if sku:
                                        line["sku"] = sku
                                        line["sku_source"] = "direct" if item.get("SellerSKU") else "order_lookup"
                                    else:
                                        line["sku"] = None
                                        line["sku_source"] = "none"
                                    
                                    financial_lines.append(line)
                                    fees_total += raw_amount
                                    logger.info(
                                        f"[FINANCES] Fee line: {fee_type} -> {line['name']} = {line['amount']} {currency_code} "
                                        f"(account={line['account_id']}, analytic={line['analytic_id']}, "
                                        f"SKU={line.get('sku', 'NONE')}, SKU_source={line.get('sku_source', 'NONE')})"
                                    )
                        
                        # ItemChargeList - Process charges (Principal, ShippingCharge, PaymentMethodFee, Tax, etc.)
                        item_charges = item.get("ItemChargeList", [])
                        for charge in item_charges:
                            charge_type = charge.get("ChargeType", "")
                            amount_dict = charge.get("ChargeAmount", {})
                            # Use CurrencyAmount (Amazon EG marketplace uses this field)
                            raw_amount = float(amount_dict.get("CurrencyAmount", 0.0))
                            currency_code = amount_dict.get("CurrencyCode", "EGP")
                            
                            # Extract Principal for product price override (one Principal per item typically)
                            if charge_type == "Principal":
                                principal_amounts.append({
                                    "amount": round(raw_amount, 2),
                                    "currency": currency_code,
                                })
                                logger.info(f"[FINANCES] Extracted Principal: {raw_amount} {currency_code} (will override product price_unit)")
                                continue
                            
                            # Skip zero-amount charges (Tax, GiftWrap, etc. that are 0)
                            if charge_type and raw_amount != 0:
                                line = self._map_charge_to_line(
                                    charge_type, raw_amount, accounting_cfg, analytics_cfg, currency_code
                                )
                                if line:
                                    # Add SKU to line if resolved
                                    if sku:
                                        line["sku"] = sku
                                        line["sku_source"] = "direct" if item.get("SellerSKU") else "order_lookup"
                                    else:
                                        line["sku"] = None
                                        line["sku_source"] = "none"
                                    
                                    financial_lines.append(line)
                                    charges_total += raw_amount
                                    logger.info(
                                        f"[FINANCES] Charge line: {charge_type} -> {line['name']} = {line['amount']} {currency_code} "
                                        f"(account={line['account_id']}, analytic={line['analytic_id']}, "
                                        f"SKU={line.get('sku', 'NONE')}, SKU_source={line.get('sku_source', 'NONE')})"
                                    )
                        
                        # PromotionList - Sales discounts/rebates
                        # Each promotion is a separate financial line (no aggregation)
                        item_promos = item.get("PromotionList", [])
                        for promo in item_promos:
                            promo_amount_dict = promo.get("PromotionAmount", {})
                            
                            # Use CurrencyAmount directly from Amazon (preserve exact value)
                            raw_amount = float(promo_amount_dict.get("CurrencyAmount", 0.0))
                            currency_code = promo_amount_dict.get("CurrencyCode", "EGP")
                            
                            # Process only non-zero amounts (preserve exact sign)
                            if raw_amount != 0:
                                amount = round(raw_amount, 2)
                                
                                financial_lines.append({
                                    "code": "PROMO_REBATE",
                                    "name": "Amazon Promotion Rebate",
                                    "amount": amount,  # Preserve exact sign from Amazon (negative for discounts)
                                    "currency": currency_code,  # Preserve exact currency from Amazon
                                    "account_id": accounting_cfg.AMAZON_PROMO_REBATES_ID,
                                    "analytic_id": analytics_cfg.AMAZON_ANALYTIC_SALES_ID,
                                })
                                promos_total += raw_amount
                                logger.info(
                                    f"[FINANCES] Promo line: PROMO_REBATE -> Amazon Promotion Rebate = {amount} {currency_code} "
                                    f"(account={accounting_cfg.AMAZON_PROMO_REBATES_ID}, "
                                    f"analytic={analytics_cfg.AMAZON_ANALYTIC_SALES_ID})"
                                )
                    
                    # Log totals summary for debugging
                    logger.info(
                        f"[FINANCES] Order {clean_id} summary: "
                        f"Charges={charges_total:.2f}, Fees={fees_total:.2f}, Promos={promos_total:.2f}"
                    )
                
                # Parse RefundEventList
                refund_events = financial_events_page.get("RefundEventList", [])
                for refund in refund_events:
                    refund_order_id = refund.get("AmazonOrderId", "")
                    if refund_order_id != clean_id:
                        continue
                    
                    for item in refund.get("ShipmentItemList", []):
                        for fee in item.get("ItemFeeList", []):
                            fee_type = fee.get("FeeType", "")
                            amount_dict = fee.get("FeeAmount", {})
                            # Use CurrencyAmount (Amazon EG marketplace uses this field)
                            raw_amount = float(amount_dict.get("CurrencyAmount", 0.0))
                            currency_code = amount_dict.get("CurrencyCode", "EGP")
                            
                            if fee_type and raw_amount != 0:
                                line = self._map_fee_to_line(
                                    fee_type, raw_amount, accounting_cfg, analytics_cfg, currency_code
                                )
                                if line:
                                    financial_lines.append(line)
                                    logger.info(f"[FINANCES] Refund fee line: {fee_type} -> {line['name']} ({line['amount']} {currency_code})")
            
            logger.info(
                f"[FINANCES] Built {len(financial_lines)} financial lines and {len(reimbursements)} "
                f"reimbursement(s) for order {clean_id}"
            )
            
            # Add Principal as metadata in first line if present (for invoice price override)
            if principal_amounts:
                # Sum all Principal amounts (typically one per item)
                total_principal = sum(p["amount"] for p in principal_amounts)
                principal_currency = principal_amounts[0]["currency"] if principal_amounts else "EGP"
                logger.info(f"[FINANCES] Total Principal extracted: {total_principal} {principal_currency}")
                # Store as special metadata in financial_lines (we'll use it in invoice creation)
                if financial_lines:
                    financial_lines[0]["_principal_total"] = total_principal
                    financial_lines[0]["_principal_currency"] = principal_currency
                else:
                    # If no other lines, add Principal as metadata line
                    financial_lines.append({
                        "code": "_PRINCIPAL_METADATA",
                        "name": "Principal (price override)",
                        "amount": total_principal,
                        "currency": principal_currency,
                        "_is_principal": True,
                    })
            
            # Store principal_items with SKU as metadata (Amazon Finances is the source of truth for SKU)
            if principal_items:
                logger.info(f"[FINANCES] Extracted {len(principal_items)} principal item(s) with SKU from Amazon Finances")
                if financial_lines:
                    financial_lines[0]["_principal_items"] = principal_items
                else:
                    # If no other lines, add Principal items as metadata line
                    financial_lines.append({
                        "code": "_PRINCIPAL_ITEMS_METADATA",
                        "name": "Principal Items (SKU source)",
                        "amount": 0,
                        "_principal_items": principal_items,
                        "_is_principal_items": True,
                    })
            
            # Store posted_dates as metadata (for invoice date extraction - ARCHITECTURAL RULE: invoice date MUST come from Amazon financial data)
            if posted_dates:
                logger.info(f"[FINANCES] Extracted {len(posted_dates)} PostedDate(s) from Amazon Finances for invoice date")
                if financial_lines:
                    financial_lines[0]["_posted_dates"] = posted_dates
                else:
                    # If no other lines, add PostedDate as metadata line
                    financial_lines.append({
                        "code": "_POSTED_DATES_METADATA",
                        "name": "PostedDate (invoice date source)",
                        "amount": 0,
                        "_posted_dates": posted_dates,
                        "_is_posted_dates": True,
                    })
            
            return financial_lines, reimbursements
            
        except Exception as e:
            logger.warning(f"Error building financial lines for order {amazon_order_id}: {e}", exc_info=True)
            return [], []
