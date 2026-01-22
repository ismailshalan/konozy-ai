from konozy_odoo_sdk.core.logger import get_logger
from konozy_odoo_sdk.core.errors import AmazonAPIError
logger = get_logger("AmazonAPI")

# ====================== ⚙️ AMAZON API ======================
import os
import re
from dotenv import load_dotenv
from sp_api.api import Orders, Finances, Reports
from sp_api.base import Marketplaces, SellingApiBadRequestException
from datetime import datetime, timedelta, timezone, timezone
from typing import Dict, List, Optional, Any, Tuple
from sp_api.api import Finances
import json
import time

load_dotenv()

def parse_posted_date(posted_after: Optional[str]) -> datetime:
    """
    Parse posted_after date with strict validation - NO fallback.
    
    ARCHITECTURAL RULE: Amazon PostedDate is the ONLY source of truth.
    This function NEVER fallbacks, guesses, or defaults.
    
    Args:
        posted_after: ISO8601 Z format datetime string (e.g., "2025-09-01T12:34:56Z")
    
    Returns:
        Timezone-aware UTC datetime object
    
    Raises:
        ValueError: If posted_after is None, empty, invalid format, or wrong type.
                   All errors include "ARCHITECTURE VIOLATION" prefix.
    """
    # Check for None or empty (including empty collections) first
    # This catches: None, "", [], {}, etc.
    if not posted_after:
        raise ValueError(
            "ARCHITECTURE VIOLATION: posted_after is required and cannot be empty"
        )
    
    # Type check: must be string (after None/empty check)
    # Non-empty non-string types should raise type error
    if not isinstance(posted_after, str):
        raise ValueError(
            f"ARCHITECTURE VIOLATION: posted_after must be string type, got {type(posted_after).__name__}"
        )
    
    # Strip whitespace before validation
    posted_after = posted_after.strip()
    
    # Check for empty or whitespace-only (after strip)
    if not posted_after:
        raise ValueError(
            "ARCHITECTURE VIOLATION: posted_after is required and cannot be empty"
        )
    
    # Must end with Z (strict ISO8601 Z format requirement)
    if not posted_after.endswith("Z"):
        raise ValueError(
            f"ARCHITECTURE VIOLATION: invalid posted_after format: {posted_after}. "
            f"Expected ISO8601 Z format (e.g., '2025-09-01T12:34:56Z')"
        )
    
    # Parse the date
    try:
        # Replace Z with +00:00 for fromisoformat
        date_str_iso = posted_after.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str_iso)
        
        # Ensure timezone-aware UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elif dt.tzinfo != timezone.utc:
            # If it has a different timezone, convert to UTC
            dt = dt.astimezone(timezone.utc)
        
        return dt
    
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"ARCHITECTURE VIOLATION: invalid posted_after format: {posted_after}. {str(e)}"
        ) from e
def _validate_iso8601_date(date_str: str) -> datetime:
    """
    Simple ISO8601 Z format validator for API parameter validation (IO-only).
    
    This is NOT the domain parser for PostedDate - that lives in AmazonFinancialSource.
    This is just format validation for API calls.
    
    Args:
        date_str: ISO8601 Z format datetime string (e.g., "2025-09-01T12:34:56Z")
    
    Returns:
        Timezone-aware UTC datetime object.
    
    Raises:
        ValueError: If date_str is invalid format.
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError(f"Invalid date format: expected ISO8601 Z format string")
    
    date_str = date_str.strip()
    if not date_str.endswith("Z"):
        raise ValueError(f"Invalid date format: expected ISO8601 Z format (e.g., '2025-09-01T12:34:56Z')")
    
    try:
        date_str_iso = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(date_str_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        raise ValueError(f"Invalid date format: {e}") from e


class AmazonAPI:
    """
    Amazon SP-API adapter.
    
    Provides pure Amazon SP-API operations with no dependencies on Odoo or other systems.
    All methods return deterministic types and handle errors gracefully.
    """
    
    def __init__(self) -> None:
        """Initialize Amazon SP-API connection."""
        self.marketplace = os.getenv("AMAZON_MARKETPLACE", "EG")
        
        # Debug test order IDs if KONOZY_DEBUG_FINANCES is enabled
        if os.getenv("KONOZY_DEBUG_FINANCES") == "1":
            self._debug_test_order_id("AMZ-402-6202063-8451542")
            self._debug_test_order_id("S02-5369777-2251569")

        self.orders_api = Orders(
            marketplace=getattr(Marketplaces, self.marketplace),
            credentials=dict(
                refresh_token=os.getenv("REFRESH_TOKEN"),
                lwa_app_id=os.getenv("LWA_APP_ID"),
                lwa_client_secret=os.getenv("LWA_CLIENT_SECRET"),
                aws_secret_key=os.getenv("AMAZON_SECRET_KEY"),
                aws_access_key=os.getenv("AMAZON_ACCESS_KEY"),
            ),
        )

    def get_orders(self, created_after: str, created_before: str) -> List[Dict[str, Any]]:
        """
        Fetch all orders from Amazon SP-API for the given date range.
        
        Handles pagination automatically via NextToken.
        
        Args:
            created_after: ISO format datetime string (e.g., "2025-01-01T00:00:00Z")
            created_before: ISO format datetime string (e.g., "2025-01-31T23:59:59Z")
        
        Returns:
            List of order dictionaries from Amazon SP-API. Empty list on error or no orders.
            Never returns None.
        """
        all_orders: List[Dict[str, Any]] = []
        next_token: Optional[str] = None
        
        while True:
            try:
                if next_token:
                    response = self.orders_api.get_orders(NextToken=next_token)
                else:
                    response = self.orders_api.get_orders(
                        CreatedAfter=created_after, CreatedBefore=created_before
                    )
                payload = response.payload
                orders = payload.get("Orders", [])
                all_orders.extend(orders)
                next_token = payload.get("NextToken")
                if not next_token:
                    break
            except SellingApiBadRequestException as e:
                logger.warning(f"Amazon API error fetching orders: {e}")
                break
        
        logger.info(f"Retrieved {len(all_orders)} orders from Amazon SP-API")
        return all_orders

    def get_order_items(self, amazon_order_id: str) -> List[Dict[str, Any]]:
        """
        Fetch order items for a specific Amazon order.
        
        Args:
            amazon_order_id: Amazon order ID (without "AMZ-" prefix)
        
        Returns:
            List of order item dictionaries. Empty list on error or no items.
            Never returns None.
        """
        try:
            response = self.orders_api.get_order_items(amazon_order_id)
            items = response.payload.get("OrderItems", [])
            return items if items else []
        except Exception as e:
            logger.error(f"Error fetching order items for {amazon_order_id}: {e}", exc_info=True)
            return []

    def fetch_order_items(self, amazon_order_id: str) -> List[Dict[str, Any]]:
        """
        Fetch order items for a specific Amazon order with pagination support.
        Returns normalized items with consistent keys.
        
        Args:
            amazon_order_id: Amazon order ID (may include "AMZ-" prefix)
        
        Returns:
            List of normalized item dictionaries with keys:
            - sku: SellerSKU
            - title: Title
            - qty: QuantityOrdered
            - asin: ASIN (if available)
            Empty list on error or no items. Never returns None.
        """
        try:
            # Normalize order ID (remove AMZ- prefix if present)
            clean_order_id = self._normalize_amazon_order_id(amazon_order_id)
            if not clean_order_id:
                logger.warning(f"[ORDERS] Invalid order ID format: {amazon_order_id}")
                return []
            
            all_items: List[Dict[str, Any]] = []
            next_token: Optional[str] = None
            
            while True:
                try:
                    # Call Orders API - get_order_items accepts OrderId as first arg and NextToken as kwarg
                    if next_token:
                        response = self.orders_api.get_order_items(clean_order_id, NextToken=next_token)
                    else:
                        response = self.orders_api.get_order_items(clean_order_id)
                    
                    payload = response.payload
                    items = payload.get("OrderItems", [])
                    
                    # Normalize items
                    for item in items:
                        normalized = {
                            "sku": item.get("SellerSKU", ""),
                            "title": item.get("Title", ""),
                            "qty": int(item.get("QuantityOrdered", 0)),
                            "asin": item.get("ASIN", ""),
                        }
                        # Only add items with valid SKU
                        if normalized["sku"]:
                            all_items.append(normalized)
                            logger.debug(f"[ORDERS] Normalized item: SKU={normalized['sku']}, Title={normalized['title']}, Qty={normalized['qty']}")
                    
                    next_token = payload.get("NextToken")
                    if not next_token:
                        break
                        
                except SellingApiBadRequestException as e:
                    logger.warning(f"[ORDERS] Amazon API error fetching order items for {clean_order_id}: {e}")
                    break
                except Exception as e:
                    logger.error(f"[ORDERS] Error fetching order items for {clean_order_id}: {e}", exc_info=True)
                    break
            
            logger.info(f"[ORDERS] Fetched {len(all_items)} item(s) for order {clean_order_id}")
            if all_items:
                skus = [item["sku"] for item in all_items]
                logger.info(f"[ORDERS] SKUs found: {', '.join(skus)}")
            return all_items
            
        except Exception as e:
            logger.error(f"[ORDERS] Fatal error fetching order items for {amazon_order_id}: {e}", exc_info=True)
            return []

    def _extract_canonical_order_id(self, raw: str) -> Optional[str]:
        """
        Extract canonical Amazon order ID from input string.
        
        Canonical format: ###-#######-####### (3-7-7 digits).
        Accepts inputs with prefixes like "AMZ-", "AMZ-S02-", "S02-", etc.
        
        Args:
            raw: Raw order ID string (may include prefixes)
        
        Returns:
            Canonical order ID string (e.g., "402-6202063-8451542") or None if not found.
        """
        if not raw:
            return None
        
        # Strip whitespace
        cleaned = raw.strip()
        
        # Search for canonical format: ###-#######-#######
        match = re.search(r"\b(\d{3}-\d{7}-\d{7})\b", cleaned)
        if match:
            return match.group(1)
        
        return None

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

    def fetch_financial_events_by_date(self, posted_after: str, posted_before: str) -> List[Dict[str, Any]]:
        """
        Fetch all raw financial events from Amazon SP-API for a date range.
        
        This method uses PostedAfter/PostedBefore instead of AmazonOrderId,
        which is more reliable for EG marketplace.
        
        Handles pagination automatically via NextToken.
        
        Args:
            posted_after: Start date in ISO format (e.g., "2025-09-01T00:00:00Z")
            posted_before: End date in ISO format (e.g., "2025-09-02T23:59:59Z")
        
        Returns:
            List of raw FinancialEvents dictionaries from Amazon SP-API.
            Each dict contains the full FinancialEvents structure.
            Empty list on error or no events. Never returns None.
        """
        try:
            refresh_token = os.getenv("REFRESH_TOKEN")
            lwa_app_id = os.getenv("LWA_APP_ID")
            lwa_client_secret = os.getenv("LWA_CLIENT_SECRET")
            aws_secret_key = os.getenv("AMAZON_SECRET_KEY")
            aws_access_key = os.getenv("AMAZON_ACCESS_KEY")

            if not all([refresh_token, lwa_app_id, lwa_client_secret, aws_secret_key, aws_access_key]):
                logger.error("Amazon SP-API credentials incomplete")
                return []

            finances_api = Finances(
                marketplace=getattr(Marketplaces, self.marketplace),
                credentials={
                    "refresh_token": refresh_token,
                    "lwa_app_id": lwa_app_id,
                    "lwa_client_secret": lwa_client_secret,
                    "aws_secret_key": aws_secret_key,
                    "aws_access_key": aws_access_key,
                },
            )

            all_financial_events: List[Dict[str, Any]] = []
            next_token: Optional[str] = None

            # Amazon requires PostedBefore < now() - 2 minutes
            # Validate date format (IO-only validation)
            try:
                posted_before_dt = _validate_iso8601_date(posted_before)
                # Check if posted_before is in the future (Amazon API requirement)
                safe_now = datetime.now(timezone.utc) - timedelta(minutes=3)
                if posted_before_dt >= safe_now:
                    posted_before = safe_now.strftime("%Y-%m-%dT%H:%M:%SZ")
                    logger.debug(f"[FINANCES] Adjusted posted_before to safe_now: {posted_before}")
            except ValueError as e:
                logger.error(f"[FINANCES] Invalid posted_before date format: {e}")
                raise

            logger.info(f"[FINANCES] Fetching financial events by date range: {posted_after} to {posted_before}")

            while True:
                try:
                    if next_token:
                        response = finances_api.list_financial_events(NextToken=next_token)
                    else:
                        response = finances_api.list_financial_events(
                            PostedAfter=posted_after,
                            PostedBefore=posted_before
                        )
                    
                    payload = response.payload
                    financial_events = payload.get("FinancialEvents", {})
                    
                    # Store the entire FinancialEvents dict for later filtering
                    if financial_events:
                        all_financial_events.append(financial_events)
                    
                    next_token = payload.get("NextToken")
                    if not next_token:
                        break
                        
                except SellingApiBadRequestException as e:
                    logger.warning(f"Amazon API error fetching financial events: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error fetching financial events: {e}", exc_info=True)
                    break

            total_events = sum(
                len(financial_events.get("ShipmentEventList", [])) +
                len(financial_events.get("RefundEventList", [])) +
                len(financial_events.get("ServiceFeeEventList", [])) +
                len(financial_events.get("RetrochargeEventList", []))
                for financial_events in all_financial_events
            )
            
            logger.info(f"[FINANCES] Fetched {len(all_financial_events)} FinancialEvents pages with {total_events} total events")
            return all_financial_events

        except Exception as e:
            logger.error(f"Error fetching financial events by date: {e}", exc_info=True)
            return []

    def get_financial_events(self, amazon_order_id: str) -> List[Dict[str, Any]]:
        """
        Fetch raw financial events for a specific Amazon order.
        
        Handles pagination automatically via NextToken.
        Only calls Finances API with canonical order ID format (###-#######-#######).
        
        Args:
            amazon_order_id: Amazon order ID (may include prefixes like "AMZ-", "S02-", etc.)
        
        Returns:
            List of fee dictionaries with structure: [{"type": str, "amount": float}, ...]
            Empty list on error or no events. Never returns None.
        """
        try:
            # Extract canonical order ID
            canonical = self._extract_canonical_order_id(amazon_order_id)
            if not canonical:
                logger.warning(f"[FINANCES] Invalid/non-canonical AmazonOrderId input={amazon_order_id!r} (skipping Finances call)")
                return []
            
            order_id = canonical
            
            logger.info(f"[FINANCES] Starting get_financial_events() for order: {order_id}")
            
            refresh_token = os.getenv("REFRESH_TOKEN")
            lwa_app_id = os.getenv("LWA_APP_ID")
            lwa_client_secret = os.getenv("LWA_CLIENT_SECRET")
            aws_secret_key = os.getenv("AMAZON_SECRET_KEY")
            aws_access_key = os.getenv("AMAZON_ACCESS_KEY")

            if not all([refresh_token, lwa_app_id, lwa_client_secret, aws_secret_key, aws_access_key]):
                logger.error("Amazon SP-API credentials incomplete")
                return []

            finances_api = Finances(
                marketplace=getattr(Marketplaces, self.marketplace),
                credentials={
                    "refresh_token": refresh_token,
                    "lwa_app_id": lwa_app_id,
                    "lwa_client_secret": lwa_client_secret,
                    "aws_secret_key": aws_secret_key,
                    "aws_access_key": aws_access_key,
                },
            )

            all_fees: List[Dict[str, Any]] = []
            next_token: Optional[str] = None
            
            # Get JSONL path for debugging
            jsonl_path = os.getenv("FINANCES_JSONL_PATH")

            while True:
                try:
                    if next_token:
                        response = finances_api.list_financial_events(NextToken=next_token)
                    else:
                        response = finances_api.list_financial_events(AmazonOrderId=order_id)
                    
                    payload = response.payload
                    financial_events = payload.get("FinancialEvents", {})
                    
                    # Parse ShipmentEventList
                    shipment_events = financial_events.get("ShipmentEventList", [])
                    for shipment in shipment_events:
                        if shipment.get("AmazonOrderId") != order_id:
                            continue
                        for item in shipment.get("ShipmentItemList", []):
                            # ItemFeeList
                            for fee in item.get("ItemFeeList", []):
                                fee_type = fee.get("FeeType", "")
                                amount_dict = fee.get("FeeAmount", {})
                                # EG payload uses "Amount" key, fallback to "CurrencyAmount"
                                amount = float(amount_dict.get("Amount") or amount_dict.get("CurrencyAmount") or 0.0)
                                if fee_type and amount != 0:
                                    fee_entry = {"type": fee_type, "amount": amount}
                                    all_fees.append(fee_entry)
                                    logger.info(f"[FINANCES][LINE] order_id={order_id} type={fee_type} amount={amount}")
                                    
                                    # Write to JSONL if enabled
                                    if jsonl_path:
                                        try:
                                            with open(jsonl_path, "a", encoding="utf-8") as f:
                                                json.dump({
                                                    "order_id": order_id,
                                                    "type": fee_type,
                                                    "amount": amount,
                                                    "source": "ItemFeeList"
                                                }, f, ensure_ascii=False)
                                                f.write("\n")
                                        except Exception as e:
                                            logger.debug(f"[FINANCES] Failed to write JSONL: {e}")
                            
                            # ItemChargeList
                            for charge in item.get("ItemChargeList", []):
                                charge_type = charge.get("ChargeType", "")
                                amount_dict = charge.get("ChargeAmount", {})
                                # EG payload uses "Amount" key, fallback to "CurrencyAmount"
                                amount = float(amount_dict.get("Amount") or amount_dict.get("CurrencyAmount") or 0.0)
                                if charge_type and amount != 0:
                                    charge_entry = {"type": charge_type, "amount": amount}
                                    all_fees.append(charge_entry)
                                    logger.info(f"[FINANCES][LINE] order_id={order_id} type={charge_type} amount={amount}")
                                    
                                    # Write to JSONL if enabled
                                    if jsonl_path:
                                        try:
                                            with open(jsonl_path, "a", encoding="utf-8") as f:
                                                json.dump({
                                                    "order_id": order_id,
                                                    "type": charge_type,
                                                    "amount": amount,
                                                    "source": "ItemChargeList"
                                                }, f, ensure_ascii=False)
                                                f.write("\n")
                                        except Exception as e:
                                            logger.debug(f"[FINANCES] Failed to write JSONL: {e}")
                    
                    # Parse RefundEventList
                    refund_events = financial_events.get("RefundEventList", [])
                    for refund in refund_events:
                        if refund.get("AmazonOrderId") != order_id:
                            continue
                        for item in refund.get("ShipmentItemList", []):
                            for fee in item.get("ItemFeeList", []):
                                fee_type = fee.get("FeeType", "")
                                amount_dict = fee.get("FeeAmount", {})
                                # EG payload uses "Amount" key, fallback to "CurrencyAmount"
                                amount = float(amount_dict.get("Amount") or amount_dict.get("CurrencyAmount") or 0.0)
                                if fee_type and amount != 0:
                                    fee_entry = {"type": fee_type, "amount": amount}
                                    all_fees.append(fee_entry)
                                    logger.info(f"[FINANCES][LINE] order_id={order_id} type={fee_type} amount={amount}")
                                    
                                    # Write to JSONL if enabled
                                    if jsonl_path:
                                        try:
                                            with open(jsonl_path, "a", encoding="utf-8") as f:
                                                json.dump({
                                                    "order_id": order_id,
                                                    "type": fee_type,
                                                    "amount": amount,
                                                    "source": "RefundFeeList"
                                                }, f, ensure_ascii=False)
                                                f.write("\n")
                                        except Exception as e:
                                            logger.debug(f"[FINANCES] Failed to write JSONL: {e}")
                    
                    next_token = payload.get("NextToken")
                    if not next_token:
                        break
                        
                except SellingApiBadRequestException as e:
                    logger.warning(f"Amazon API error fetching financial events for {order_id}: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error fetching financial events for order {order_id}: {e}", exc_info=True)
                    break

            logger.info(f"[FINANCES] Parsed {len(all_fees)} fees for order {order_id}")
            return all_fees

        except Exception as e:
            logger.error(f"Error fetching financial events for order {amazon_order_id}: {e}", exc_info=True)
            return []

    def get_refunds_by_date_range(self, posted_after: str, posted_before: str) -> List[Dict[str, Any]]:
        """
        Fetch refund events (returns) from Amazon SP-API Finances for a date range.
        
        Handles pagination automatically via NextToken.
        
        Args:
            posted_after: Start date in ISO format (e.g., "2025-09-01T00:00:00Z")
            posted_before: End date in ISO format (e.g., "2025-12-01T23:59:59Z")
        
        Returns:
            List of refund event dictionaries from Amazon SP-API.
            Empty list on error or no refunds. Never returns None.
        """
        try:
            refresh_token = os.getenv("REFRESH_TOKEN")
            lwa_app_id = os.getenv("LWA_APP_ID")
            lwa_client_secret = os.getenv("LWA_CLIENT_SECRET")
            aws_secret_key = os.getenv("AMAZON_SECRET_KEY")
            aws_access_key = os.getenv("AMAZON_ACCESS_KEY")

            if not all([refresh_token, lwa_app_id, lwa_client_secret, aws_secret_key, aws_access_key]):
                logger.error("Amazon SP-API credentials incomplete")
                return []

            finances_api = Finances(
                marketplace=getattr(Marketplaces, self.marketplace),
                credentials={
                    "refresh_token": refresh_token,
                    "lwa_app_id": lwa_app_id,
                    "lwa_client_secret": lwa_client_secret,
                    "aws_secret_key": aws_secret_key,
                    "aws_access_key": aws_access_key,
                },
            )

            all_refund_events: List[Dict[str, Any]] = []
            next_token: Optional[str] = None

            # Amazon requires PostedBefore < now() - 2 minutes
            # Validate date format (IO-only validation)
            try:
                posted_before_dt = _validate_iso8601_date(posted_before)
                # Check if posted_before is in the future (Amazon API requirement)
                safe_now = datetime.now(timezone.utc) - timedelta(minutes=3)
                if posted_before_dt >= safe_now:
                    posted_before = safe_now.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError as e:
                # ARCHITECTURAL RULE: Fail hard on invalid date - NO fallback
                logger.error(f"[REFUNDS] ARCHITECTURE VIOLATION: Invalid posted_before date: {e}")
                raise

            while True:
                try:
                    if next_token:
                        response = finances_api.list_financial_events(NextToken=next_token)
                    else:
                        response = finances_api.list_financial_events(
                            PostedAfter=posted_after,
                            PostedBefore=posted_before
                        )
                    
                    events = response.payload.get("FinancialEvents", {})
                    refund_events = events.get("RefundEventList", [])
                    all_refund_events.extend(refund_events)
                    
                    next_token = response.payload.get("NextToken")
                    if not next_token:
                        break
                        
                except SellingApiBadRequestException as e:
                    logger.warning(f"Amazon API error fetching refunds: {e}")
                    break

            logger.info(f"Retrieved {len(all_refund_events)} refund events from Amazon")
            return all_refund_events

        except Exception as e:
            logger.error(f"Error fetching refunds: {e}", exc_info=True)
            return []

    def get_fba_shipments_via_reports(self) -> Optional[str]:
        """
        Generate and retrieve FBA inventory summary report URL.
        
        Creates a report, waits for it to be ready, then returns the download URL.
        
        Returns:
            Report download URL as string if successful.
            None on error or if URL not available.
        """
        try:
            reports_api = Reports(
                marketplace=getattr(Marketplaces, self.marketplace),
                credentials=dict(
                    refresh_token=os.getenv("REFRESH_TOKEN"),
                    lwa_app_id=os.getenv("LWA_APP_ID"),
                    lwa_client_secret=os.getenv("LWA_CLIENT_SECRET"),
                    aws_secret_key=os.getenv("AMAZON_SECRET_KEY"),
                    aws_access_key=os.getenv("AMAZON_ACCESS_KEY"),
                ),
            )

            logger.info("Creating FBA Inventory Summary Report...")
            create_report = reports_api.create_report(reportType="GET_FBA_FULFILLMENT_INVENTORY_SUMMARY_DATA")
            report_id = create_report.payload.get("reportId")

            if not report_id:
                logger.error("Report creation failed: no report ID returned")
                return None

            logger.info(f"Waiting for report {report_id} to be ready...")
            time.sleep(30)  # Wait for report generation

            report_document = reports_api.get_report_document(report_id)
            url = report_document.payload.get("url")

            if url:
                logger.info(f"Report ready for download: {url}")
                return url
            else:
                logger.warning("Report generated but URL not found")
                return None

        except Exception as e:
            logger.error(f"Error fetching FBA report: {e}", exc_info=True)
            return None
