import ssl
import xmlrpc.client
import os
import socket
import time
from typing import Any, List, Dict, Optional, Tuple
import logging
import asyncio
from core.application.interfaces import IOdooClient
from core.settings.modules.odoo_settings import OdooSettings

logger = logging.getLogger(__name__)
# Set socket timeout globally
socket.setdefaulttimeout(35)

# Import ConfigFactory for lazy-loaded configuration
# No validation happens at import time

# Module-level config instances (required by architecture guards)

import logging
logger = logging.getLogger("OdooClient")

class OdooClient:
    """
    Odoo XML-RPC adapter.
    
    Provides pure Odoo operations with no dependencies on Amazon or other marketplaces.
    All methods are idempotent where applicable and return deterministic types.
    """
    
    @property
    def _accounting_cfg(self):
        """Lazy-loaded accounting configuration."""
        return get_factory().get_accounting()
    
    @property
    def _analytics_cfg(self):
        """Lazy-loaded analytics configuration."""
        return get_factory().get_analytics()
    
    def __init__(self) -> None:
        """Initialize Odoo XML-RPC connection."""
        self.url = Config.ODOO_URL
        self.db = Config.ODOO_DB
        self.username = Config.ODOO_USER
        self.password = Config.ODOO_PASSWORD
        self.current_order_date: Optional[str] = None
        context = ssl._create_unverified_context()
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", context=context)
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            if not self.uid:
                raise Exception("Authentication failed. Check DB, username, or password.")
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", context=context)
            logger.info(f"Connected to Odoo | DB: {self.db} | UID: {self.uid}")
        except ssl.SSLError as e:
            logger.warning(f"SSL verification failed: {e}")
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", context=context)

    def safe_execute_kw(self, model: str, method: str, *args: Any, **kwargs: Any) -> Optional[Any]:
        """
        Safe wrapper for Odoo XML-RPC execute_kw calls with retry logic.
        
        This is the ONLY low-level XML-RPC gateway. All other methods use this.
        
        Automatically sanitizes None values for create/write operations to prevent
        XML-RPC marshalling errors.
        
        Args:
            model: Odoo model name (e.g., "sale.order")
            method: Odoo method name (e.g., "search", "create", "write")
            *args: Positional arguments for execute_kw
            **kwargs: Keyword arguments for execute_kw
        
        Returns:
            Result from Odoo XML-RPC call, or None on error.
            Return type depends on the Odoo method called.
        """
        # Global sanitization: Remove None values for create/write operations
        # This prevents XML-RPC marshalling errors at the boundary
        if method in ("create", "write") and args:
            sanitized_args = list(args)
            if method == "create":
                # create: args[0] is [dict] or [list of dicts]
                if sanitized_args[0] and isinstance(sanitized_args[0], list):
                    sanitized_args[0] = [self._sanitize_vals(item) for item in sanitized_args[0]]
            elif method == "write":
                # write: args[0] is [[ids], dict] - sanitize the dict (second element)
                if sanitized_args[0] and isinstance(sanitized_args[0], list) and len(sanitized_args[0]) >= 2:
                    # Sanitize the values dict (second element: args[0][1])
                    if isinstance(sanitized_args[0][1], dict):
                        sanitized_args[0][1] = self._sanitize_vals(sanitized_args[0][1])
            args = tuple(sanitized_args)
        
        retries = 3
        last_exception = None
        
        for attempt in range(retries):
            try:
                return self.models.execute_kw(self.db, self.uid, self.password, model, method, *args, **kwargs)
            except (BrokenPipeError, socket.timeout, TimeoutError) as e:
                last_exception = e
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 1  # Exponential backoff: 1s, 2s, 3s
                    logger.warning(
                        f"XML-RPC timeout/pipe error in {model}.{method} (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"XML-RPC Error in {model}.{method} after {retries} attempts: {e}", exc_info=True)
            except KeyboardInterrupt:
                # Don't retry on KeyboardInterrupt, just re-raise
                raise
            except Exception as e:
                # For other exceptions, log and return None (no retry)
                logger.error(f"XML-RPC Error in {model}.{method}: {e}", exc_info=True)
                return None
        
        # If we exhausted retries, return None
        return None

    # ---------------------------------------------
    # ✅ Safe Field Helpers (for optional custom fields)
    # ---------------------------------------------

    def get_model_fields(self, model: str) -> Dict[str, Any]:
        """
        Get all fields for a model using Odoo fields_get.
        
        Args:
            model: Odoo model name (e.g., "account.move", "sale.order")
        
        Returns:
            Dictionary of field names to field definitions, or empty dict on error.
        """
        try:
            fields = self.safe_execute_kw(
                model,
                "fields_get",
                [],
                {}
            )
            if fields and isinstance(fields, dict):
                return fields
            return {}
        except Exception as e:
            logger.warning(f"[SAFE_FIELD] Failed to get fields for {model}: {e}", exc_info=True)
            return {}

    def safe_add(self, vals: dict, model: str, field: str, value: Any) -> None:
        """
        Safely adds a field to Odoo create/write vals only if the field exists.
        Prevents crashes when custom fields are missing.
        
        Args:
            vals: Dictionary of values to add field to (modified in-place)
            model: Odoo model name (e.g., "account.move", "sale.order")
            field: Field name to check and add (e.g., "x_processing_order")
            value: Value to set if field exists
        """
        try:
            fields = self.get_model_fields(model)
            if field in fields:
                vals[field] = value
            else:
                logger.debug(
                    f"[SAFE_FIELD] {model}.{field} not present, skipping"
                )
        except Exception as e:
            logger.warning(
                f"[SAFE_FIELD] Failed checking {model}.{field} ({e}), skipping"
            )

    # ---------------------------------------------
    # ✅ XML-RPC Sanitization Helpers
    # ---------------------------------------------

    def _sanitize_vals(self, vals: Any) -> Any:
        """
        Recursively remove None values from dictionaries and nested structures.
        
        XML-RPC does NOT allow None values. This helper ensures all None values
        are removed before sending to Odoo, handling:
        - Simple dictionaries
        - Lists of dictionaries
        - Nested structures like one2many fields: [(0, 0, {...})]
        
        Args:
            vals: Value to sanitize (dict, list, tuple, or other)
        
        Returns:
            Sanitized value with None values removed
        """
        if isinstance(vals, dict):
            # Remove None values and recursively sanitize nested dicts
            sanitized = {}
            for k, v in vals.items():
                if v is not None:
                    sanitized[k] = self._sanitize_vals(v)
            return sanitized
        elif isinstance(vals, list):
            # Handle lists (including one2many tuples like [(0, 0, {...})])
            sanitized = []
            for item in vals:
                if item is not None:
                    sanitized.append(self._sanitize_vals(item))
            return sanitized
        elif isinstance(vals, tuple):
            # Handle tuples (one2many commands: (0, 0, {...}))
            sanitized = []
            for item in vals:
                if item is not None:
                    sanitized.append(self._sanitize_vals(item))
            return tuple(sanitized)
        else:
            # Primitive types (int, str, bool, etc.) - return as-is
            return vals

    # ---------------------------------------------
    # ✅ Sale Order Helpers
    # ---------------------------------------------

    def find_sale_order_by_name(self, name: str) -> Optional[int]:
        """
        Find sale order by name (idempotent).
        
        Args:
            name: Sale order name to search for
        
        Returns:
            Sale order ID if found, None otherwise.
        """
        ids = self.safe_execute_kw(
            "sale.order",
            "search",
            [[["name", "=", name]]],
            {"limit": 1},
        )
        if not ids or not isinstance(ids, list) or len(ids) == 0:
            return None
        return int(ids[0]) if ids else None

    # ---------------------------------------------
    # ✅ Invoice Helpers
    # ---------------------------------------------

    def find_invoice_by_ref(self, ref: str) -> Optional[int]:
        """
        Find customer invoice by reference (idempotent).
        
        Args:
            ref: Invoice reference to search for
        
        Returns:
            Invoice ID if found, None otherwise.
        """
        ids = self.safe_execute_kw(
            "account.move",
            "search",
            [[
                ["move_type", "=", "out_invoice"],
                ["ref", "=", ref],
            ]],
            {"limit": 1},
        )
        if not ids or not isinstance(ids, list) or len(ids) == 0:
            return None
        return int(ids[0]) if ids else None

    def link_invoice_to_sale_order(self, sale_order_id: int, invoice_id: int) -> None:
        """
        Link an invoice to a sale order (idempotent).
        
        Args:
            sale_order_id: Sale order ID
            invoice_id: Invoice ID to link
        
        Returns:
            None. Errors are logged but not raised.
        """
        write_vals = {"invoice_ids": [(4, invoice_id)]}
        write_vals = self._sanitize_vals(write_vals)
        self.safe_execute_kw(
            "sale.order",
            "write",
            [[sale_order_id], write_vals],
        )

    # =========================================================
    
    # =========================================================
    def _get_or_create_service_product(self, code: str, product_name: str, source: str = "amazon") -> Optional[int]:
        """
        Get or create a service product for marketplace fees.
        
        Args:
            code: Financial line code (e.g., "COMMISSION", "SHIPPING_CHARGE", "REFERRAL_FEE")
            product_name: Product name to create if not found
            source: Marketplace source ("amazon" or "noon"), defaults to "amazon" for backward compatibility
        
        Returns:
            Product ID if found or created, None on error.
        """
        try:
            # Construct environment variable name from code
            # Handle special cases and normalize code
            code_upper = code.upper().replace("-", "_")
            source_upper = source.upper()
            env_var_name = f"{source_upper}_{code_upper}_ID"
            
            # Check if product ID is already in environment
            product_id_str = os.getenv(env_var_name)
            if product_id_str:
                try:
                    product_id = int(product_id_str)
                    # Verify product exists
                    product = self.safe_execute_kw(
                        "product.product", "read",
                        [[product_id]],
                        {"fields": ["id"]}
                    )
                    if product and isinstance(product, list) and len(product) > 0:
                        logger.debug(f"[SERVICE] Found existing service product {product_name} (ID={product_id}) from {env_var_name}")
                        return product_id
                except (ValueError, TypeError):
                    pass
            
            # Search for existing product by name
            existing = self.safe_execute_kw(
                "product.product", "search_read",
                [[["name", "=", product_name], ["type", "=", "service"]]],
                {"fields": ["id"], "limit": 1}
            )
            
            if existing and isinstance(existing, list) and len(existing) > 0:
                product_id = int(existing[0]["id"])
                logger.info(f"[SERVICE] Found existing service product {product_name} (ID={product_id}) from {source_upper} {code_upper}")
                # Store in environment for future use (optional - could use cache instead)
                os.environ[env_var_name] = str(product_id)
                return product_id
            
            # Create new service product
            template_vals = {
                "name": product_name,
                "type": "service",
                "invoice_policy": "order",
                "list_price": 0,
                "taxes_id": False,
                "sale_ok": True,
            }
            template_vals = self._sanitize_vals(template_vals)
            template = self.safe_execute_kw(
                "product.template", "create",
                [template_vals]
            )
            
            if not template or not isinstance(template, list) or len(template) == 0:
                logger.error(f"[SERVICE] Failed to create service product template for {product_name}")
                return None
            
            template_id = int(template[0].get("value", 0)) if isinstance(template[0], dict) else int(template[0])
            
            # Get product variant
            variant = self.safe_execute_kw(
                "product.product", "search_read",
                [[["product_tmpl_id", "=", template_id]]],
                {"fields": ["id"], "limit": 1}
            )
            
            if variant and isinstance(variant, list) and len(variant) > 0:
                product_id = int(variant[0]["id"])
                logger.info(f"[SERVICE] Created service product {product_name} (ID={product_id}) for {source_upper} {code_upper}")
                # Store in environment for future use
                os.environ[env_var_name] = str(product_id)
                return product_id
            
            logger.error(f"[SERVICE] Failed to find product variant for {product_name}")
            return None
            
        except Exception as e:
            logger.error(f"[SERVICE] Error getting/creating service product {product_name}: {e}", exc_info=True)
            return None

    # =========================================================
    def get_commission_for_product(self, product_id: int) -> Tuple[float, float, Optional[int]]:
        """
        DEPRECATED: This method is deprecated and should NOT be used.
        
        Amazon Finances API is now the ONLY source of truth for commissions, fees, and charges.
        Odoo must NEVER calculate Amazon fees again.
        
        This method returns (0.0, 0.0, None) to maintain backward compatibility
        but all commission logic has been removed from invoice creation.
        
        Args:
            product_id: Product ID (ignored)
        
        Returns:
            Tuple of (0.0, 0.0, None) - always returns zero values.
        """
        logger.warning(
            f"[DEPRECATED] get_commission_for_product called for product {product_id}. "
            "This method is deprecated. Use Amazon Finances API data instead."
        )
        return (0.0, 0.0, None)

    # =========================================================
    def _resolve_accounting_datetime(
        self,
        financial_lines: Optional[List[Dict[str, Any]]] = None,
        order_date: Optional[str] = None,
    ) -> str:
        """
        Resolve accounting datetime from Amazon Finances PostedDate (SINGLE SOURCE OF TRUTH).
        
        ARCHITECTURAL RULE: Amazon Finances PostedDate is the ONLY source of truth for accounting date.
        This method extracts PostedDate and returns a DATETIME string for Odoo (sale.order.date_order is DATETIME field).
        
        Args:
            financial_lines: Optional financial lines from Amazon Finances API (for extracting PostedDate)
            order_date: Optional fallback date (format: "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SSZ")
        
        Returns:
            DATETIME string in format "YYYY-MM-DD 12:00:00" (use 12:00 to avoid timezone shifting)
        
        Logs:
            - Which path was used (PostedDate vs fallback vs utcnow)
        """
        from datetime import datetime, timezone
        
        # Try to extract PostedDate from financial_lines metadata
        if financial_lines:
            posted_dates = None
            for line in financial_lines:
                if line.get("_posted_dates"):
                    posted_dates = line["_posted_dates"]
                    break
                elif line.get("code") == "_POSTED_DATES_METADATA":
                    posted_dates = line.get("_posted_dates")
                    break
            
            if posted_dates:
                try:
                    # Find minimum (earliest) PostedDate from Amazon financial events
                    parsed_dates = []
                    for posted_date_str in posted_dates:
                        try:
                            # Parse ISO format: "2025-09-01T12:34:56Z"
                            if "T" in posted_date_str:
                                dt = datetime.fromisoformat(posted_date_str.replace("Z", "+00:00"))
                            else:
                                dt = datetime.fromisoformat(posted_date_str)
                            parsed_dates.append(dt.date())
                        except (ValueError, AttributeError):
                            continue
                    
                    if parsed_dates:
                        earliest_date = min(parsed_dates)
                        accounting_dt = f"{earliest_date.strftime('%Y-%m-%d')} 12:00:00"
                        logger.info(f"[DATE] Accounting datetime resolved from Amazon Finances PostedDate: {accounting_dt}")
                        return accounting_dt
                    else:
                        logger.warning(f"[DATE] Could not parse any PostedDate from financial_lines, using fallback")
                except Exception as e:
                    logger.warning(f"[DATE] Error extracting PostedDate from financial_lines: {e}, using fallback")
        
        # Fallback to order_date parameter if provided
        if order_date:
            try:
                # Normalize order_date to date string, then add time
                if "T" in order_date:
                    date_part = order_date.split("T")[0]
                else:
                    date_part = order_date[:10] if len(order_date) >= 10 else order_date
                
                # Validate date format
                datetime.strptime(date_part, "%Y-%m-%d")  # Will raise ValueError if invalid
                accounting_dt = f"{date_part} 12:00:00"
                logger.info(f"[DATE] Accounting datetime from order_date parameter (fallback): {accounting_dt}")
                return accounting_dt
            except (ValueError, AttributeError) as e:
                logger.warning(f"[DATE] Invalid order_date format '{order_date}': {e}, using utcnow() as last resort")
        
        # LAST RESORT: Use current UTC time (but log it loudly)
        utc_now = datetime.now(timezone.utc)
        accounting_dt = f"{utc_now.strftime('%Y-%m-%d')} 12:00:00"
        logger.error(
            f"[DATE] ⚠️ WARNING: No PostedDate or valid order_date available - using utcnow() as LAST RESORT: {accounting_dt}. "
            f"This should NOT happen in production. Check Amazon Finances API integration."
        )
        return accounting_dt
    
    # =========================================================
    def create_customer_invoice(
        self,
        partner_id: int,
        order_lines: List[Tuple[int, int, float]],
        order_name: str,
        order_date: str,
        sale_order_id: int,
        financial_lines: Optional[List[Dict[str, Any]]] = None,
        accounting_dt: Optional[str] = None,
    ) -> Optional[int]:

        try:
            # ============================
            # 0) Resolve Accounting Datetime (SINGLE SOURCE OF TRUTH)
            # ============================
            # ARCHITECTURAL RULE: Amazon Finances PostedDate is the ONLY source of truth for accounting date.
            # If accounting_dt is provided, use it directly (guarantees consistency with Sale Order).
            # Otherwise, resolve from financial_lines or order_date.
            if accounting_dt:
                # Use provided accounting_dt (ensures Sale Order and Invoice use same date)
                logger.info(f"[DATE] Accounting datetime provided explicitly: {accounting_dt}")
                accounting_date = accounting_dt[:10]  # Extract date part for invoice_date (date-only field)
            else:
                # Resolve accounting datetime from financial_lines or order_date
                accounting_dt = self._resolve_accounting_datetime(financial_lines, order_date)
                accounting_date = accounting_dt[:10]  # Extract date part for invoice_date (date-only field)
            
            logger.info(f"[DATE] Accounting datetime resolved from Finances PostedDate: {accounting_dt} (invoice_date={accounting_date})")
            
            # ============================
            # 1) Invoice Idempotency Check (ARCHITECTURAL RULE)
            # ============================
            # ARCHITECTURAL RULE: Each AmazonOrderId MUST produce at most ONE customer invoice.
            # Check for existing invoice by invoice_origin before creating any invoice lines.
            existing_invoices = self.safe_execute_kw(
                "account.move",
                "search_read",
                [[
                    ("move_type", "=", "out_invoice"),
                    ("invoice_origin", "=", order_name)
                ]],
                {"fields": ["id"], "limit": 1}
            )
            
            if existing_invoices and len(existing_invoices) > 0:
                existing_invoice_id = existing_invoices[0]["id"]
                logger.info(f"Invoice already exists for {order_name}, reusing it (ID={existing_invoice_id})")
                return int(existing_invoice_id)
            
            # ============================
            # 2) Read Sale Order & Lines
            # ============================
            sale_order = self.safe_execute_kw(
                "sale.order", "read",
                [[sale_order_id]],
                {"fields": ["order_line"]}
            )

            if not sale_order or not sale_order[0].get("order_line"):
                logger.warning(f"[INVOICE] No sale order lines for order {order_name}")
                return None

            sale_line_ids = sale_order[0]["order_line"]

            so_lines = self.safe_execute_kw(
                "sale.order.line", "read",
                [sale_line_ids],
                {"fields": ["id", "product_id"]}
            ) or []

            # Build mapping: product_id -> sale.order.line.id (for backward compatibility)
            # AND SKU -> sale.order.line.id (for proper linkage via Amazon Finances SKU)
            # CRITICAL: The ONLY valid linkage in Odoo is via account.move.line.sale_line_ids
            # SKU appears in invoice ONLY when sale_line_ids is set
            product_to_so_line = {}
            sku_to_so_line: Dict[str, int] = {}  # SKU -> sale.order.line.id mapping
            
            # First, get all product IDs from sale order lines
            product_ids = []
            for line in so_lines:
                pid = line.get("product_id")
                so_line_id = line.get("id")
                if isinstance(pid, (list, tuple)) and pid and so_line_id:
                    product_id = int(pid[0])
                    product_ids.append(product_id)
                    product_to_so_line[product_id] = int(so_line_id)
                    logger.debug(f"[INVOICE] Mapped product_id={product_id} -> sale.order.line ID={so_line_id}")
            
            # Fetch products to get SKU (default_code) for mapping
            product_cache: Dict[int, Dict[str, str]] = {}
            if product_ids:
                products = self.safe_execute_kw(
                    "product.product", "read",
                    [product_ids],
                    {"fields": ["id", "default_code", "name"]}
                ) or []
                for product in products:
                    product_id = product.get("id")
                    if product_id:
                        default_code = product.get("default_code", "")
                        product_cache[product_id] = {
                            "default_code": default_code,
                            "name": product.get("name", "")
                        }
                        # Build SKU -> sale.order.line.id mapping
                        if default_code and product_id in product_to_so_line:
                            sku_to_so_line[default_code] = product_to_so_line[product_id]
                            logger.info(f"[LINK] SKU={default_code} -> sale.order.line.id={product_to_so_line[product_id]}")
                            
                            # Detect placeholder SKUs (e.g., "AMZ-{order_id}")
                            if default_code.startswith("AMZ-") and len(default_code.split("-")) == 2:
                                logger.warning(
                                    f"[WARN] Placeholder SKU detected for order {order_name}: {default_code}. "
                                    f"This prevents correct linkage. Use real Amazon SellerSKU instead."
                                )
            
            # Log mapping summary
            if sku_to_so_line:
                logger.info(f"[LINK] Built SKU mapping for SO {order_name}: {len(sku_to_so_line)} SKUs")
            if not product_to_so_line:
                logger.warning(f"[WARN] No product-to-sale-line mapping found for order {order_name} - SKU will not appear in invoice")
            if not sku_to_so_line:
                logger.warning(f"[WARN] No SKU-to-sale-line mapping found for order {order_name} - invoice lines may not link properly")

            # ============================
            # 2) Extract Principal items from financial_lines (Amazon Finances is the source of truth for SKU)
            # ============================
            principal_items = None
            if financial_lines:
                # Check if Principal items metadata is stored in first line
                first_line = financial_lines[0]
                if first_line.get("_principal_items") is not None:
                    principal_items = first_line["_principal_items"]
                    logger.info(f"[INVOICE] Using Principal items from Amazon Finances: {len(principal_items)} item(s) with SKU")
                # Also check for _PRINCIPAL_ITEMS_METADATA line
                if not principal_items:
                    for line in financial_lines:
                        if line.get("_principal_items") is not None:
                            principal_items = line["_principal_items"]
                            logger.info(f"[INVOICE] Using Principal items from Amazon Finances: {len(principal_items)} item(s) with SKU")
                            break

            # ============================
            # 2) Build Product Sales Invoice Lines (AGGREGATED BY SKU)
            # ============================
            invoice_lines = []

            # Product sales lines (revenue) - Build ONLY from Amazon Finances data
            # Ignore order_lines as SKU source - Amazon Finances is the ONLY source of truth
            # ARCHITECTURAL RULE: Each product must appear ONCE per order (aggregated by SKU)
            if principal_items:
                logger.info(f"[INVOICE] Building product invoice lines from Amazon Finances (ignoring order_lines)")
                
                # STEP 1: Aggregate principal_items by SKU
                # Build in-memory map keyed by SKU: {sku: {"qty": sum, "principal_amount": sum, "currency": str}}
                aggregated_products: Dict[str, Dict[str, Any]] = {}
                for principal_item in principal_items:
                    sku = principal_item.get("sku", "")
                    qty = principal_item.get("qty", 1)
                    principal_amount = principal_item.get("principal_amount", 0.0)
                    currency = principal_item.get("currency", "EGP")
                    
                    if not sku:
                        logger.warning(f"[WARN] Skipping principal item with missing SKU")
                        continue
                    
                    if principal_amount == 0:
                        logger.warning(f"[WARN] Skipping principal item with zero amount: SKU={sku}")
                        continue
                    
                    # Aggregate by SKU: sum quantities and amounts
                    if sku not in aggregated_products:
                        aggregated_products[sku] = {
                            "qty": 0,
                            "principal_amount": 0.0,
                            "currency": currency
                        }
                    
                    aggregated_products[sku]["qty"] += qty
                    aggregated_products[sku]["principal_amount"] += principal_amount
                
                logger.info(f"[INVOICE] Aggregated {len(principal_items)} principal item(s) into {len(aggregated_products)} unique SKU(s)")
                
                # STEP 2: Create ONE invoice line per aggregated product (SKU)
                for sku, agg_data in aggregated_products.items():
                    total_qty = agg_data["qty"]
                    total_principal_amount = agg_data["principal_amount"]
                    currency = agg_data["currency"]
                    
                    # Log SKU resolved from Amazon Finances
                    logger.info(f"[LINK] SKU resolved from Amazon Finances: {sku} (aggregated: qty={total_qty}, amount={total_principal_amount})")
                    
                    # Calculate price_unit = total_principal_amount / total_qty
                    price_unit = total_principal_amount / total_qty if total_qty > 0 else total_principal_amount
                    
                    # ARCHITECTURAL RULE: Amazon Finances MUST NEVER create products
                    # Products must already exist from Amazon Orders API (Sale Order creation)
                    # If product doesn't exist, it's an error - product should have been created from Orders API
                    product_id = self.find_product(sku)
                    if not product_id:
                        logger.error(
                            f"[INVOICE] Product not found for SKU={sku} - "
                            f"product should have been created from Amazon Orders API. Skipping invoice line."
                        )
                        continue
                    
                    logger.info(f"[INVOICE] Found existing product for SKU={sku} (product_id={product_id})")
                    
                    # Build invoice line name with SKU
                    line_name = f"[{sku}] Amazon Product"
                    
                    line_vals = {
                        "product_id": product_id,
                        "quantity": total_qty,
                        "price_unit": price_unit,
                        "account_id": self._accounting_cfg.AMAZON_SALES_ID,
                        "analytic_distribution": {
                            str(self._analytics_cfg.AMAZON_ANALYTIC_SALES_ID): 100.0
                        },
                        "name": line_name,
                    }
                    
                    # CRITICAL: Link invoice line to sale order line via sale_line_ids
                    # This is the ONLY valid linkage in Odoo for proper traceability
                    # Match by SKU (default_code) to find corresponding sale.order.line
                    # ⚠️ This linkage applies ONLY to product revenue lines (Principal)
                    # ⚠️ Financial lines (commission, FBA, shipping, promo) must NOT be linked
                    so_line_id = sku_to_so_line.get(sku)
                    if so_line_id:
                        line_vals["sale_line_ids"] = [(6, 0, [so_line_id])]
                        logger.info(
                            f"[LINK] Linked invoice product line to sale.order.line.id={so_line_id} for SKU={sku}"
                        )
                    else:
                        logger.warning(
                            f"[WARN] No matching sale.order.line for SKU={sku} in {order_name} -> linkage skipped"
                        )
                    
                    logger.info(f"[INVOICE] Product line from Amazon Finances: {line_name} (product_id={product_id}, qty={total_qty}, price_unit={price_unit})")
                    invoice_lines.append((0, 0, line_vals))
            else:
                # Fallback to order_lines if principal_items not available (backward compatibility)
                logger.warning(f"[INVOICE] No principal_items found in financial_lines, falling back to order_lines")
                principal_override = None
                if financial_lines:
                    # Check if Principal metadata is stored in first line
                    first_line = financial_lines[0]
                    if first_line.get("_principal_total") is not None:
                        principal_override = first_line["_principal_total"]
                        logger.info(f"[INVOICE] Using Principal override: {principal_override} (from Amazon Finances)")
                    # Also check for _PRINCIPAL_METADATA line
                    for line in financial_lines:
                        if line.get("code") == "_PRINCIPAL_METADATA":
                            principal_override = line.get("amount")
                            logger.info(f"[INVOICE] Using Principal override: {principal_override} (from Amazon Finances)")
                            break
                
                # Product sales lines (revenue)
                # Override price_unit with Principal from Amazon if available
                for idx, (product_id, qty, original_price_unit) in enumerate(order_lines):
                    so_line_id = product_to_so_line.get(product_id)
                    
                    # Use Principal override if available (typically one Principal per invoice for single-item orders)
                    # For multi-item orders, use Principal for first product (can be enhanced later with SKU matching)
                    if principal_override is not None and idx == 0:
                        price_unit = principal_override / qty if qty > 0 else principal_override
                        logger.info(
                            f"[INVOICE] Overriding product price_unit: {original_price_unit} -> {price_unit} "
                            f"(using Principal={principal_override} from Amazon Finances)"
                        )
                    else:
                        price_unit = original_price_unit

                    # Build invoice line name with SKU for better visibility
                    product_info = product_cache.get(product_id, {})
                    default_code = product_info.get("default_code", "")
                    product_name = product_info.get("name", "")
                    
                    # Set invoice line name explicitly with SKU: "[SKU] Product Name"
                    if default_code:
                        line_name = f"[{default_code}] {product_name}"
                    else:
                        line_name = product_name if product_name else "Product"
                    
                    line_vals = {
                        "product_id": product_id,
                        "quantity": qty,
                        "price_unit": price_unit,
                        "account_id": self._accounting_cfg.AMAZON_SALES_ID,
                        "analytic_distribution": {
                            str(self._analytics_cfg.AMAZON_ANALYTIC_SALES_ID): 100.0
                        },
                        "name": line_name,  # Explicitly set name with SKU
                    }

                    # CRITICAL: Link invoice line to sale order line via sale_line_ids
                    # This is the ONLY valid linkage in Odoo for proper traceability
                    # Try SKU-based matching first (preferred), then fallback to product_id matching
                    so_line_id = None
                    if default_code:
                        # Try SKU-based matching first (more reliable)
                        so_line_id = sku_to_so_line.get(default_code)
                        if so_line_id:
                            logger.info(
                                f"[LINK] Linked invoice product line to sale.order.line.id={so_line_id} for SKU={default_code}"
                            )
                    
                    # Fallback to product_id matching if SKU matching failed
                    if not so_line_id:
                        so_line_id = product_to_so_line.get(product_id)
                        if so_line_id:
                            logger.info(
                                f"[LINK] Linked invoice product line to sale.order.line.id={so_line_id} "
                                f"for product_id={product_id} (SKU: {default_code or 'NONE'})"
                            )
                    
                    if so_line_id:
                        line_vals["sale_line_ids"] = [(6, 0, [so_line_id])]
                    else:
                        logger.warning(
                            f"[WARN] No matching sale.order.line for SKU={default_code or 'NONE'} in {order_name} -> linkage skipped"
                        )

                    logger.info(f"[INVOICE] Product line: {line_name} (product_id={product_id}, qty={qty}, price_unit={price_unit})")
                    invoice_lines.append((0, 0, line_vals))

            # ============================
            # 3) Financial Lines (FEES/ADJUSTMENTS - AGGREGATED BY FEE_TYPE)
            # Amazon Finances API is the ONLY source of truth
            # ARCHITECTURAL RULE: Fees must be aggregated by (order_id, fee_type) to prevent duplicates
            # ============================
            # Filter out Principal metadata (not a real financial line)
            filtered_financial_lines = [
                line for line in (financial_lines or [])
                if line.get("code") != "_PRINCIPAL_METADATA" 
                and line.get("code") != "_PRINCIPAL_ITEMS_METADATA"
                and not line.get("_is_principal")
                and not line.get("_is_principal_items")
            ]
            
            if not filtered_financial_lines:
                logger.warning(
                    f"[INVOICE] No financial_lines provided for {order_name}. "
                    "Invoice will only contain product sales lines (no fees/commissions from Amazon Finances)."
                )
            else:
                logger.info(f"[INVOICE] Processing {len(filtered_financial_lines)} financial lines from Amazon Finances for {order_name}")
                
                # STEP 1: Aggregate fees by fee_type (code)
                # Build in-memory map keyed by code: {code: {"amount": sum, "name": str, "account_id": int, "analytic_id": int}}
                aggregated_fees: Dict[str, Dict[str, Any]] = {}
                for financial_line in filtered_financial_lines:
                    try:
                        amount = float(financial_line.get("amount", 0.0))
                        
                        # Skip ONLY if amount == 0
                        if amount == 0:
                            logger.debug(f"[INVOICE] Skipping financial line with zero amount: {financial_line.get('name', 'Unknown')}")
                            continue
                        
                        # Extract required fields (already validated by AmazonAPI.build_financial_lines_for_order)
                        code = financial_line.get("code", "")
                        name = financial_line.get("name", "Amazon Fee")
                        account_id = financial_line.get("account_id")
                        analytic_id = financial_line.get("analytic_id")
                        
                        # Validate required fields
                        if not account_id or not analytic_id:
                            logger.error(
                                f"[INVOICE] Missing account_id or analytic_id for {name} (code={code}). "
                                "Skipping - this should not happen. Financial line is malformed."
                            )
                            continue
                        
                        # Aggregate by code (fee_type): sum amounts
                        if code not in aggregated_fees:
                            aggregated_fees[code] = {
                                "amount": 0.0,
                                "name": name,
                                "account_id": account_id,
                                "analytic_id": analytic_id
                            }
                        
                        aggregated_fees[code]["amount"] += amount
                        
                    except Exception as e:
                        logger.error(f"[INVOICE] Error processing financial line {financial_line}: {e}", exc_info=True)
                        # Continue with next line - don't crash on single line error
                        continue
                
                logger.info(f"[INVOICE] Aggregated {len(filtered_financial_lines)} financial line(s) into {len(aggregated_fees)} unique fee type(s)")
                
                # STEP 2: Create ONE invoice line per aggregated fee type
                for code, agg_data in aggregated_fees.items():
                    total_amount = agg_data["amount"]
                    name = agg_data["name"]
                    account_id = agg_data["account_id"]
                    analytic_id = agg_data["analytic_id"]
                    
                    # Get or create service product using code directly (no hardcoded mapping)
                    product_id = self._get_or_create_service_product(code, name)
                    
                    if not product_id:
                        logger.error(f"[INVOICE] Failed to get/create service product for {name} (code={code}), skipping")
                        continue
                    
                    # Create invoice line - preserve exact Amazon values (aggregated amount)
                    # ⚠️ IMPORTANT: Financial lines (commission, FBA, shipping, promo) must NOT be linked
                    # to sale orders. Do NOT set sale_line_ids here - linkage applies ONLY to product revenue lines.
                    invoice_lines.append((0, 0, {
                        "product_id": product_id,
                        "quantity": 1,
                        "price_unit": total_amount,  # Aggregated amount (preserve exact sign from Amazon)
                        "account_id": account_id,  # From Amazon Finances API
                        "analytic_distribution": {
                            str(analytic_id): 100.0  # From Amazon Finances API
                        },
                        "name": name,  # From Amazon Finances API
                        # NOTE: sale_line_ids is intentionally NOT set for financial lines
                    }))
                    
                    logger.info(f"[INVOICE] Added aggregated financial line: {name} (code={code}, amount={total_amount}) using account {account_id}, analytic {analytic_id}")

            # ============================
            # 4) Calculate Invoice Total and Skip if Zero
            # ============================
            # Calculate total from invoice lines
            invoice_total = 0.0
            for line_tuple in invoice_lines:
                if len(line_tuple) >= 3 and isinstance(line_tuple[2], dict):
                    line_vals = line_tuple[2]
                    quantity = float(line_vals.get("quantity", 1))
                    price_unit = float(line_vals.get("price_unit", 0.0))
                    invoice_total += quantity * price_unit
            
            # If invoice total is 0, skip invoice creation
            if invoice_total == 0:
                logger.info(f"[INVOICE] Skipping invoice creation for {order_name} - total is 0")
                return None

            # Log invoice totals before creation
            logger.info(f"[INVOICE] Invoice totals before creation for {order_name}: {invoice_total} EGP ({len(invoice_lines)} lines)")

            # ============================
            # 5) Create Invoice
            # ============================
            invoice_vals = {
                "move_type": "out_invoice",
                "partner_id": partner_id,
                "journal_id": self._accounting_cfg.AMAZON_JOURNAL_ID,
                "invoice_date": accounting_date,  # Use centralized accounting_date from Amazon Finances PostedDate
                "ref": order_name,
                "invoice_origin": order_name,
                "invoice_payment_term_id": False,
                "invoice_line_ids": invoice_lines,
            }
            invoice_vals = self._sanitize_vals(invoice_vals)

            invoice_id = self.safe_execute_kw(
                "account.move", "create",
                [invoice_vals]
            )

            if isinstance(invoice_id, list):
                invoice_id = invoice_id[0]
            invoice_id = int(invoice_id)

            logger.info(f"[INVOICE] Created invoice ID={invoice_id}")

            # ============================
            # 6) Post Invoice
            # ============================
            self.safe_execute_kw(
                "account.move", "action_post",
                [[invoice_id]]
            )

            logger.info(f"[INVOICE] Posted invoice {invoice_id}")

            # ============================
            # 7) Validate Invoice - Detect Duplicate Product Lines
            # ============================
            # ARCHITECTURAL RULE: Each product must appear ONCE per order.
            # This validation ensures no duplicate product lines exist in the invoice.
            invoice_data = self.safe_execute_kw(
                "account.move",
                "read",
                [[invoice_id]],
                {"fields": ["invoice_line_ids"]}
            )
            
            if invoice_data and isinstance(invoice_data, list) and len(invoice_data) > 0:
                line_ids = invoice_data[0].get("invoice_line_ids", [])
                if line_ids:
                    # Read all invoice lines to check for duplicate products
                    lines = self.safe_execute_kw(
                        "account.move.line",
                        "read",
                        [line_ids],
                        {"fields": ["product_id", "name"]}
                    ) or []
                    
                    # Track product IDs seen in invoice lines
                    product_ids_seen: Dict[int, List[str]] = {}  # product_id -> list of line names
                    
                    for line in lines:
                        product_id_field = line.get("product_id")
                        if product_id_field:
                            product_id = int(product_id_field[0]) if isinstance(product_id_field, (list, tuple)) else int(product_id_field)
                            line_name = line.get("name", "")
                            
                            # Only check product lines (not service/fee lines)
                            # Service products are typically created dynamically and may have same product_id
                            # We check by product type: if it's a "product" type, it must be unique
                            product_info = self.safe_execute_kw(
                                "product.product",
                                "read",
                                [[product_id]],
                                {"fields": ["type"]}
                            )
                            
                            if product_info and isinstance(product_info, list) and len(product_info) > 0:
                                product_type = product_info[0].get("type", "")
                                # Only validate "product" type (storable products), not "service" (fees)
                                if product_type == "product":
                                    if product_id in product_ids_seen:
                                        # Duplicate product detected!
                                        duplicate_line_names = product_ids_seen[product_id] + [line_name]
                                        raise AssertionError(
                                            f"FATAL ARCHITECTURE VIOLATION: Duplicate product lines detected in invoice {invoice_id} for {order_name}. "
                                            f"Product ID {product_id} appears multiple times. "
                                            f"Line names: {duplicate_line_names}. "
                                            f"Each product SKU MUST appear exactly ONCE per invoice. "
                                            f"This indicates aggregation logic failure - investigate immediately."
                                        )
                                    product_ids_seen[product_id] = [line_name]
                    
                    logger.info(f"[VALIDATION] Invoice {invoice_id} validated: {len(product_ids_seen)} unique product(s), no duplicates detected")

            # ============================
            # 8) Link Invoice → Sale Order (Backward Compatibility)
            # ============================
            # NOTE: Writing invoice_ids on sale.order is NOT sufficient for proper linkage.
            # The ONLY valid linkage in Odoo is via account.move.line.sale_line_ids (implemented above).
            # This write is kept for backward compatibility but should NOT be relied upon.
            self.safe_execute_kw(
                "sale.order", "write",
                [[sale_order_id], {"invoice_ids": [(4, invoice_id)]}]
            )

            logger.info(f"[INVOICE] Invoice {invoice_id} created and linked to sale order {sale_order_id} via sale_line_ids")

            return invoice_id

        except Exception as e:
            logger.error(f"[INVOICE] Error creating customer invoice: {e}", exc_info=True)
            return None

    # =========================================================
    def create_reimbursement_entry(
        self,
        order_name: str,
        reimbursement: Dict[str, Any],
    ) -> Optional[int]:
        """
        Create a Vendor Bill (Amazon) or Miscellaneous Journal Entry for FBA Inventory Reimbursement.
        
        Reimbursements for customer-damaged items must NOT be treated as sales products.
        Creates accounting entry with:
        - Debit: Inventory Loss / Damaged Goods account
        - Credit: Amazon Account (receivable)
        - No product, no SKU, no quantity
        
        Args:
            order_name: Order name for reference (e.g., "AMZ-402-6202063-8451542")
            reimbursement: Reimbursement dictionary with structure:
                {
                    "event_type": str,      # e.g. "FBA_INVENTORY_REIMBURSEMENT"
                    "amount": float,         # Reimbursement amount (positive)
                    "currency": str,        # Currency code
                    "order_id": str,        # Amazon order ID
                    "sku": Optional[str],   # SKU if resolved
                    "posted_date": str,      # Posted date from Amazon
                    "sku_source": str        # "direct", "order_lookup", or "none"
                }
        
        Returns:
            Journal entry ID if successful, None on error.
        """
        try:
            accounting_cfg = self._accounting_cfg
            
            amount = float(reimbursement.get("amount", 0.0))
            currency = reimbursement.get("currency", "EGP")
            event_type = reimbursement.get("event_type", "FBA_INVENTORY_REIMBURSEMENT")
            order_id = reimbursement.get("order_id", "")
            sku = reimbursement.get("sku")
            sku_source = reimbursement.get("sku_source", "none")
            posted_date = reimbursement.get("posted_date", "")
            
            if amount == 0:
                logger.warning(f"[REIMBURSEMENT] Zero amount reimbursement for {order_name}, skipping")
                return None
            
            # Extract date from posted_date or use current date
            move_date = "2025-01-01"  # Default fallback
            if posted_date:
                try:
                    # Parse ISO format date: "2025-09-01T12:34:56Z"
                    if "T" in posted_date:
                        move_date = posted_date.split("T")[0]
                    else:
                        move_date = posted_date[:10] if len(posted_date) >= 10 else posted_date
                except Exception:
                    pass
            
            # Build move lines
            move_lines: List[Tuple[int, int, Dict[str, Any]]] = []
            
            # Debit line: Inventory Loss / Damaged Goods account
            move_lines.append((0, 0, {
                "account_id": accounting_cfg.INVENTORY_LOSS_DAMAGED_GOODS_ID,
                "debit": amount,
                "credit": 0.0,
                "name": f"FBA Inventory Reimbursement - {order_name} "
                       f"(Order: {order_id}, SKU: {sku or 'NONE'}, Source: {sku_source})",
            }))
            
            # Credit line: Amazon Account (receivable)
            move_lines.append((0, 0, {
                "account_id": accounting_cfg.AMAZON_ACCOUNT_ID,
                "debit": 0.0,
                "credit": amount,
                "name": f"Amazon Reimbursement - {order_name}",
            }))
            
            # Create journal entry (miscellaneous entry)
            move_vals = {
                "move_type": "entry",
                "journal_id": accounting_cfg.AMAZON_JOURNAL_ID,
                "ref": f"{order_name} - {event_type}",
                "date": move_date,
                "line_ids": move_lines,
            }
            move_vals = self._sanitize_vals(move_vals)
            
            move_id = self.safe_execute_kw(
                "account.move", "create",
                [move_vals]
            )
            
            # Normalize return format
            if isinstance(move_id, int):
                move_id_int = move_id
            elif isinstance(move_id, list) and len(move_id) > 0:
                move_id_int = int(move_id[0]) if isinstance(move_id[0], int) else int(move_id[0])
            else:
                logger.error(f"[REIMBURSEMENT] Unexpected move ID format: {move_id}")
                return None
            
            logger.info(
                f"[REIMBURSEMENT] Journal Entry created: ID={move_id_int} for {order_name}: "
                f"amount={amount} {currency}, event_type={event_type}, "
                f"order_id={order_id}, SKU={sku or 'NONE'}, SKU_source={sku_source}"
            )
            
            # Post journal entry
            self.safe_execute_kw(
                "account.move", "action_post",
                [[move_id_int]]
            )
            logger.info(f"[REIMBURSEMENT] Journal Entry posted successfully: ID={move_id_int}")
            
            return move_id_int
            
        except Exception as e:
            logger.error(
                f"[REIMBURSEMENT] Error creating reimbursement entry for {order_name}: {e}",
                exc_info=True
            )
            return None

    # =========================================================
    def create_accounting_move(
        self,
        invoice_id: int,
        order_name: str,
        financial_events: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Create an accounting move (journal entry) for Amazon fees and commissions.
        
        Args:
            invoice_id: Invoice ID to link accounting move to
            order_name: Order name for reference
            financial_events: List of financial event dicts with structure:
                [{"type": str, "amount": float}, ...]
                Example: [{"type": "Commission", "amount": 15.0}, {"type": "FBAFees", "amount": 5.0}]
        
        Returns:
            Accounting move ID if successful, None on error.
        """
        try:
            if not financial_events:
                logger.warning(f"No financial events provided for accounting move {order_name}")
                return None

            # Build move lines
            move_lines: List[Tuple[int, int, Dict[str, Any]]] = []
            total_debit = 0.0

            # Map fee types to account IDs and analytic IDs
            for event in financial_events:
                fee_type = event.get("type", "").upper()
                amount = float(event.get("amount", 0.0))
                
                if amount == 0:
                    continue

                # Determine account and analytic based on fee type
                if "COMMISSION" in fee_type:
                    account_id = ACCOUNTING_CFG.AMAZON_COMMISSIONS_ID
                    analytic_id = ANALYTICS_CFG.AMAZON_COMMISSIONS_ANALYTIC_ID
                elif "FBA" in fee_type or "PICK" in fee_type or "PACK" in fee_type:
                    account_id = ACCOUNTING_CFG.AMAZON_FBA_PICK_PACK_FEE_ID
                    analytic_id = ANALYTICS_CFG.ANALYTIC_AMAZON_SHIPPING_COST_ID
                elif "COD" in fee_type:
                    account_id = ACCOUNTING_CFG.AMAZON_COD_FEE_ID
                    analytic_id = ANALYTICS_CFG.ANALYTIC_AMAZON_SHIPPING_COST_ID
                else:
                    # Default to commissions account for unknown fee types
                    account_id = ACCOUNTING_CFG.AMAZON_COMMISSIONS_ID
                    analytic_id = ANALYTICS_CFG.AMAZON_COMMISSIONS_ANALYTIC_ID

                # Debit line (expense)
                move_lines.append((0, 0, {
                    "account_id": account_id,
                    "debit": amount,
                    "credit": 0.0,
                    "name": f"{fee_type} - {order_name}",
                    "analytic_distribution": {str(analytic_id): 100.0},
                }))
                total_debit += amount

            if not move_lines:
                logger.warning(f"No valid move lines for accounting move {order_name}")
                return None

            # Credit line (Amazon receivable)
            move_lines.append((0, 0, {
                "account_id": ACCOUNTING_CFG.AMAZON_ACCOUNT_ID,
                "debit": 0.0,
                "credit": total_debit,
                "name": f"Amazon Fees - {order_name}",
            }))

            # Get invoice date for accounting move
            invoice = self.safe_execute_kw(
                "account.move", "read",
                [[invoice_id]],
                {"fields": ["invoice_date", "date"]}
            )
            move_date = "2025-01-01"  # Default fallback
            if invoice and isinstance(invoice, list) and len(invoice) > 0:
                invoice_date = invoice[0].get("invoice_date") or invoice[0].get("date")
                if invoice_date:
                    if isinstance(invoice_date, str):
                        move_date = invoice_date[:10] if len(invoice_date) >= 10 else invoice_date
                    else:
                        move_date = str(invoice_date)[:10]

            # Create accounting move
            move_vals = {
                "move_type": "entry",
                "journal_id": ACCOUNTING_CFG.AMAZON_JOURNAL_ID,
                "ref": f"{order_name} - Fees",
                "date": move_date,
                "line_ids": move_lines,
            }
            move_vals = self._sanitize_vals(move_vals)

            move_id = self.models.execute_kw(
                self.db, self.uid, self.password,
                "account.move", "create",
                [move_vals]
            )

            # Normalize return format
            if isinstance(move_id, int):
                move_id_int = move_id
            elif isinstance(move_id, list) and len(move_id) > 0:
                move_id_int = int(move_id[0]) if isinstance(move_id[0], int) else int(move_id[0].get("id", move_id[0].get("value", 0)))
            else:
                logger.error(f"Unexpected accounting move ID format: {move_id}")
                return None

            logger.info(f"Accounting move created with ID={move_id_int} for {order_name}")

            # Post accounting move
            self.models.execute_kw(
                self.db, self.uid, self.password,
                "account.move", "action_post",
                [[move_id_int]]
            )
            logger.info(f"Accounting move posted successfully: {move_id_int}")

            return move_id_int

        except Exception as e:
            logger.error(f"Error creating accounting move: {e}", exc_info=True)
            return None

    # =========================================================
    def create_or_find_partner(
            self, 
            name: str, 
            email: Optional[str] = None, 
            order_id: Optional[str] = None,
            shipping_address: Optional[Dict[str, Any]] = None
        ) -> int:
            """
            Find or create a partner (idempotent).
            
            Args:
                name: Partner name
                email: Optional email address
                order_id: Optional order ID for naming (creates "AMZ-{order_id}" format)
                shipping_address: Optional shipping address dictionary
            
            Returns:
                Partner ID. Returns fallback partner ID on error.
            """
            try:
                parent_id = Config.AMAZON_PARTNER_ID or 19
                child_name = f"AMZ-{order_id}" if order_id else name

                existing = self.safe_execute_kw(
                    "res.partner", "search_read",
                    [[["name", "=", child_name], ["parent_id", "=", parent_id]]],
                    {"fields": ["id"], "limit": 1}
                )
                if existing and isinstance(existing, list) and len(existing) > 0:
                    partner_id = int(existing[0]["id"])
                    logger.info(f"Partner already exists: {child_name} (ID={partner_id})")
                else:
                    created = self.safe_execute_kw(
                        "res.partner", "create",
                        [{
                            "name": child_name,
                            "email": email or False,
                            "customer_rank": 1,
                            "type": "contact",
                            "parent_id": parent_id,
                            "company_type": "person",
                            "comment": "Auto-created from Amazon order",
                        }]
                    )
                    if not created or not isinstance(created, list) or len(created) == 0:
                        logger.error("Failed to create partner")
                        return parent_id
                    partner_id = int(created[0].get("value", 0)) if isinstance(created[0], dict) else int(created[0])
                    logger.info(f"Created new partner: {child_name} (ID={partner_id})")

                if shipping_address:
                    try:
                        vals: Dict[str, Any] = {
                            "name": f"{child_name} - Shipping",
                            "type": "delivery",
                            "parent_id": partner_id,
                            "street": shipping_address.get("AddressLine1", ""),
                            "city": shipping_address.get("City", ""),
                            "zip": shipping_address.get("PostalCode", ""),
                        }
                        code = shipping_address.get("CountryCode", "")
                        if code:
                            country = self.safe_execute_kw(
                                "res.country", "search_read",
                                [[["code", "=", code]]], {"fields": ["id"], "limit": 1}
                            )
                            if country and isinstance(country, list) and len(country) > 0:
                                vals["country_id"] = country[0]["id"]
                        self.safe_execute_kw("res.partner", "create", [vals])
                        logger.info(f"Shipping address created for: {child_name}")
                    except Exception as e:
                        logger.error(f"Error creating shipping address: {e}", exc_info=True)
                return partner_id
            except Exception as e:
                logger.error(f"Error in partner creation: {e}", exc_info=True)
                return Config.AMAZON_PARTNER_ID or 19

    # =========================================================
    
    def find_product(self, sku: str) -> Optional[int]:
        """
        Find product by SKU (default_code) with optional barcode fallback.

        ARCHITECTURAL GUARANTEE:
        - NO product creation
        - Searches by default_code first, then barcode if not found
        - Returns None if not found

        Args:
            sku: Product SKU/default_code (or barcode as fallback)

        Returns:
            Product ID if found, None otherwise
        """
        if not sku:
            return None

        try:
            # First, search by default_code
            result = self.safe_execute_kw(
                "product.product",
                "search_read",
                [[["default_code", "=", sku]]],
                {"fields": ["id"], "limit": 1}
            )
            if result:
                product_id = int(result[0]["id"])
                logger.debug(f"[PRODUCT] Found product by default_code={sku} (ID={product_id})")
                return product_id

            # Fallback: search by barcode (optional)
            result = self.safe_execute_kw(
                "product.product",
                "search_read",
                [[["barcode", "=", sku]]],
                {"fields": ["id"], "limit": 1}
            )
            if result:
                product_id = int(result[0]["id"])
                logger.debug(f"[PRODUCT] Found product by barcode={sku} (ID={product_id})")
                return product_id

            return None

        except Exception as e:
            logger.error(
                f"[PRODUCT] Failed to find product for SKU={sku}: {e}",
                exc_info=True
            )
            return None
    
    def ensure_noon_sequence_exists(self) -> bool:
        """
        Ensure Noon sales order sequence exists (idempotent).
        Creates or updates ir.sequence with code "sale.order.noon" and prefix "NEG".
        
        Returns:
            True if sequence exists/created, False on error
        """
        try:
            # Search for existing sequence
            seq_ids = self.safe_execute_kw(
                "ir.sequence",
                "search",
                [[["code", "=", "sale.order.noon"]]],
                {"limit": 1}
            )
            
            if seq_ids:
                logger.info(f"Noon sequence already exists (ID={seq_ids[0]})")
                return True
            
            # Create new sequence
            seq_vals = {
                "name": "Noon Sales Order Sequence",
                "code": "sale.order.noon",
                "prefix": "NEG",
                "padding": 9,
                "implementation": "standard",
                "use_date_range": False,
            }
            
            seq_id = self.safe_execute_kw(
                "ir.sequence",
                "create",
                [seq_vals]
            )
            
            if isinstance(seq_id, list):
                seq_id = seq_id[0]
            seq_id = int(seq_id)
            
            logger.info(f"Created Noon sequence (ID={seq_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure Noon sequence exists: {e}", exc_info=True)
            return False
    
    def get_next_noon_sequence(self) -> Optional[str]:
        """
        Get next sequence number from Noon sequence (code: "sale.order.noon").
        Returns format: "NEGXXXXXXXXX" (prefix NEG + 9-digit number).
        
        Returns:
            Next sequence number string (e.g., "NEG000000123"), None on error
        """
        try:
            # Ensure sequence exists first
            if not self.ensure_noon_sequence_exists():
                return None
            
            # Get next sequence number
            next_number = self.safe_execute_kw(
                "ir.sequence",
                "next_by_code",
                ["sale.order.noon"]
            )
            
            if not next_number:
                logger.error("Failed to get next Noon sequence number")
                return None
            
            return str(next_number)
            
        except Exception as e:
            logger.error(f"Failed to get next Noon sequence: {e}", exc_info=True)
            return None
    
    def create_invoice_from_sale_order_wizard(self, sale_order_id: int) -> Optional[List[int]]:
        """
        Create invoices from sale order using sale.advance.payment.inv wizard (public method, Odoo 19 compatible).
        Returns list of invoice IDs created (usually one invoice).
        
        Args:
            sale_order_id: Sale order ID
            
        Returns:
            List of invoice IDs, or None on error
        """
        try:
            # Create wizard with advance_payment_method='delivered' (matches Amazon behavior)
            wizard_vals = {
                "advance_payment_method": "delivered",
            }
            
            wizard_id = self.safe_execute_kw(
                "sale.advance.payment.inv",
                "create",
                [wizard_vals]
            )
            
            if not wizard_id:
                logger.error(f"Failed to create invoice wizard for sale order {sale_order_id}")
                return None
            
            # Normalize wizard_id to int
            if isinstance(wizard_id, list):
                wizard_id = wizard_id[0]
            wizard_id = int(wizard_id)
            
            # Call create_invoices() method on wizard - context must be passed via execute_kw
            # The wizard reads active_ids from context, so we need to pass context correctly
            # Note: In Odoo XML-RPC, context is passed as a keyword argument in execute_kw
            result = self.models.execute_kw(
                self.db, self.uid, self.password,
                "sale.advance.payment.inv",
                "create_invoices",
                [[wizard_id]],
                {
                    "context": {
                        "active_model": "sale.order",
                        "active_ids": [sale_order_id],
                    }
                }
            )
            
            # Read sale order to get invoice_ids after creation
            so_data = self.safe_execute_kw(
                "sale.order",
                "read",
                [[sale_order_id]],
                {"fields": ["invoice_ids"]}
            )
            
            if not so_data or not isinstance(so_data, list) or len(so_data) == 0:
                logger.error(f"Could not read sale order {sale_order_id} to get invoice IDs")
                return None
            
            invoice_ids = so_data[0].get("invoice_ids", [])
            
            if not invoice_ids:
                logger.error(f"No invoices created from sale order {sale_order_id}")
                return None
            
            invoice_ids = [int(inv_id) for inv_id in invoice_ids if inv_id]
            
            logger.info(f"Created {len(invoice_ids)} invoice(s) from sale order {sale_order_id} via wizard: {invoice_ids}")
            return invoice_ids
            
        except Exception as e:
            logger.error(f"Failed to create invoices from sale order {sale_order_id}: {e}", exc_info=True)
            return None
    
    def find_sale_order_by_external_ref(self, external_ref: str) -> Optional[int]:
        """
        Find sale order by external reference (client_order_ref or origin).
        
        Args:
            external_ref: External reference string (e.g., "NOON:order_nr")
            
        Returns:
            Sale order ID if found, None otherwise
        """
        try:
            so_ids = self.safe_execute_kw(
                "sale.order",
                "search",
                [[
                    "|",
                    ("client_order_ref", "=", external_ref),
                    ("origin", "=", external_ref),
                ]],
                {"limit": 1}
            )
            
            if so_ids and len(so_ids) > 0:
                return int(so_ids[0])
            return None
            
        except Exception as e:
            logger.error(f"Error finding sale order by external_ref {external_ref}: {e}", exc_info=True)
            return None
    
    def find_invoice_by_origin(self, origin: str, draft_only: bool = False) -> Optional[int]:
        """
        Find invoice by invoice_origin.
        
        Args:
            origin: Invoice origin (usually sale order name)
            draft_only: If True, only search for draft invoices
            
        Returns:
            Invoice ID if found, None otherwise
        """
        try:
            domain = [
                ("move_type", "=", "out_invoice"),
                ("invoice_origin", "=", origin),
            ]
            
            if draft_only:
                domain.append(("state", "=", "draft"))
            else:
                domain.append(("state", "in", ("draft", "posted")))
            
            inv_ids = self.safe_execute_kw(
                "account.move",
                "search",
                [domain],
                {"limit": 1}
            )
            
            if inv_ids and len(inv_ids) > 0:
                return int(inv_ids[0])
            return None
            
        except Exception as e:
            logger.error(f"Error finding invoice by origin {origin}: {e}", exc_info=True)
            return None
    
    def add_fee_lines_to_invoice(
        self,
        invoice_id: int,
        fee_lines: List[Dict[str, Any]],
        external_ref: str,
    ) -> int:
        """
        Add fee lines to invoice with idempotency check.
        Each fee line is identified by a stable key: "NOON_FEE:{external_ref}:{code}"
        
        Args:
            invoice_id: Invoice ID
            fee_lines: List of fee line dictionaries with keys: code, name, amount, account_id, analytic_id
            external_ref: External reference for idempotency key (e.g., "NOON:order_nr")
            
        Returns:
            Number of fee lines added (excluding duplicates)
        """
        try:
            # Read existing invoice lines to check for duplicates
            inv_data = self.safe_execute_kw(
                "account.move",
                "read",
                [[invoice_id]],
                {"fields": ["invoice_line_ids"]}
            )
            
            existing_line_names = set()
            if inv_data and isinstance(inv_data, list) and len(inv_data) > 0:
                line_ids = inv_data[0].get("invoice_line_ids", [])
                if line_ids:
                    lines = self.safe_execute_kw(
                        "account.move.line",
                        "read",
                        [line_ids],
                        {"fields": ["name"]}
                    ) or []
                    existing_line_names = {line.get("name", "") for line in lines}
            
            # Build invoice lines to add (with idempotency key in name)
            invoice_lines_to_add = []
            added_count = 0
            
            for fee_line in fee_lines:
                code = fee_line.get("code", "")
                name = fee_line.get("name", "Noon Fee")
                amount = fee_line.get("amount", 0.0)
                account_id = fee_line.get("account_id")
                analytic_id = fee_line.get("analytic_id")
                product_id = fee_line.get("product_id")
                
                # Build stable idempotency key
                idempotency_key = f"NOON_FEE:{external_ref}:{code}"
                line_name = f"{name} [{idempotency_key}]"
                
                # Skip if line already exists
                if line_name in existing_line_names:
                    logger.debug(f"Fee line {idempotency_key} already exists in invoice {invoice_id}, skipping")
                    continue
                
                # Skip if required fields missing
                if not account_id or not analytic_id or not product_id:
                    logger.warning(f"Missing required fields for fee line {code}, skipping")
                    continue
                
                # Skip zero amounts
                if abs(float(amount)) < 0.01:
                    continue
                
                invoice_lines_to_add.append((0, 0, {
                    "product_id": product_id,
                    "quantity": 1,
                    "price_unit": amount,
                    "account_id": account_id,
                    "analytic_distribution": {
                        str(analytic_id): 100.0
                    },
                    "name": line_name,
                }))
                added_count += 1
            
            # Add lines to invoice
            if invoice_lines_to_add:
                self.safe_execute_kw(
                    "account.move",
                    "write",
                    [[invoice_id], {
                        "invoice_line_ids": invoice_lines_to_add,
                    }],
                )
                logger.info(f"Added {added_count} fee line(s) to invoice {invoice_id}")
            
            return added_count
            
        except Exception as e:
            logger.error(f"Error adding fee lines to invoice {invoice_id}: {e}", exc_info=True)
            return 0
    
    def clear_invoice_lines(self, invoice_id: int) -> None:
        """
        Clear all invoice lines from an invoice.
        
        Safely removes all account.move.line records associated with the invoice.
        Only works on draft invoices.
        
        Args:
            invoice_id: Invoice ID (account.move)
        
        Raises:
            Exception: If invoice cannot be cleared (e.g., not in draft state)
        """
        try:
            # Read invoice to get line IDs
            invoice_data = self.safe_execute_kw(
                "account.move",
                "read",
                [[invoice_id]],
                {"fields": ["invoice_line_ids", "state"]}
            )
            
            if not invoice_data or len(invoice_data) == 0:
                logger.warning(f"[INVOICE] Invoice {invoice_id} not found, cannot clear lines")
                return
            
            invoice_state = invoice_data[0].get("state", "draft")
            if invoice_state != "draft":
                raise ValueError(f"Cannot clear lines from invoice {invoice_id} - invoice is in {invoice_state} state (must be draft)")
            
            line_ids = invoice_data[0].get("invoice_line_ids", [])
            if not line_ids:
                logger.debug(f"[INVOICE] Invoice {invoice_id} has no lines to clear")
                return
            
            # Delete all invoice lines
            self.safe_execute_kw(
                "account.move.line",
                "unlink",
                [line_ids]
            )
            
            logger.info(f"[INVOICE] Cleared {len(line_ids)} line(s) from invoice {invoice_id}")
            
        except Exception as e:
            logger.error(f"Error clearing invoice lines from invoice {invoice_id}: {e}", exc_info=True)
            raise
    
    def write_invoice_lines(self, invoice_id: int, invoice_lines: List[tuple]) -> None:
        """
        Write invoice lines to an invoice.
        
        Adds new invoice lines to an existing invoice using Odoo's invoice_line_ids format.
        The invoice must be in draft state.
        
        Args:
            invoice_id: Invoice ID (account.move)
            invoice_lines: List of (0, 0, {...}) tuples for invoice_line_ids format
        
        Raises:
            Exception: If invoice lines cannot be written
        """
        try:
            if not invoice_lines:
                logger.debug(f"[INVOICE] No invoice lines to write to invoice {invoice_id}")
                return
            
            # Write invoice lines using unlink + create pattern
            # First, read current invoice state
            invoice_data = self.safe_execute_kw(
                "account.move",
                "read",
                [[invoice_id]],
                {"fields": ["state"]}
            )
            
            if not invoice_data or len(invoice_data) == 0:
                raise ValueError(f"Invoice {invoice_id} not found")
            
            invoice_state = invoice_data[0].get("state", "draft")
            if invoice_state != "draft":
                raise ValueError(f"Cannot write lines to invoice {invoice_id} - invoice is in {invoice_state} state (must be draft)")
            
            # Write invoice lines
            write_vals = {"invoice_line_ids": invoice_lines}
            write_vals = self._sanitize_vals(write_vals)
            self.safe_execute_kw(
                "account.move",
                "write",
                [[invoice_id], write_vals]
            )
            
            logger.info(f"[INVOICE] Wrote {len(invoice_lines)} line(s) to invoice {invoice_id}")
            
        except Exception as e:
            logger.error(f"Error writing invoice lines to invoice {invoice_id}: {e}", exc_info=True)
            raise
    
    def create_sale_order(
        self, 
        order_name: str, 
        partner_id: int,
        order_lines: List[Tuple[int, int, float]],
        order_date: str,
        warehouse_id: Optional[int] = None,
        buyer_metadata: Optional[Dict[str, Optional[str]]] = None,
        financial_lines: Optional[List[Dict[str, Any]]] = None,
        accounting_dt: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create and confirm a sale order (idempotent if order_name is unique).

        ARCHITECTURAL RULE:
        - sale.order.date_order MUST come from Amazon Finances PostedDate (accounting_dt).
        - Odoo may override date_order during action_confirm(), so we re-apply it AFTER confirm.
        - Existing Sale Orders are NEVER updated (idempotency preserved).
        """

        if not order_date and not accounting_dt:
            raise AssertionError(
                "ARCHITECTURAL VIOLATION: Sale Order must be created with Amazon PostedDate"
            )

        try:
            warehouse_id = warehouse_id or Config.AMAZON_WAREHOUSE_ID or 1

            # =====================================================
            # Resolve accounting datetime (SINGLE SOURCE OF TRUTH)
            # =====================================================
            if accounting_dt:
                logger.info(f"[DATE] Accounting datetime provided explicitly: {accounting_dt}")
            else:
                accounting_dt = self._resolve_accounting_datetime(financial_lines, order_date)

            logger.info(f"[DATE] Creating Sale Order with accounting_dt={accounting_dt}")

            # =====================================================
            # Build Sale Order values
            # =====================================================
            order_vals = {
                "name": order_name,
                "partner_id": partner_id,
                "warehouse_id": warehouse_id,
                "date_order": accounting_dt,  # DATETIME field
                "order_line": [
                    (0, 0, {
                        "product_id": p,
                        "product_uom_qty": q,
                        "price_unit": u
                    })
                    for p, q, u in order_lines
                ],
            }

            # Buyer metadata (optional)
            if buyer_metadata:
                metadata_parts = []
                if buyer_metadata.get("amazon_order_id"):
                    metadata_parts.append(f"Amazon Order: {buyer_metadata['amazon_order_id']}")
                if buyer_metadata.get("buyer_name"):
                    metadata_parts.append(f"Buyer: {buyer_metadata['buyer_name']}")
                if buyer_metadata.get("buyer_email"):
                    metadata_parts.append(f"Email: {buyer_metadata['buyer_email']}")

                if metadata_parts:
                    metadata_str = " | ".join(metadata_parts)
                    order_vals["client_order_ref"] = metadata_str
                    order_vals["note"] = f"Amazon Buyer Info:\n{metadata_str}"

            # =====================================================
            # Create Sale Order
            # =====================================================
            logger.info(f"[ORDERS] Creating Sale Order: {order_name}")
            order_vals = self._sanitize_vals(order_vals)
            order = self.models.execute_kw(
                self.db, self.uid, self.password,
                "sale.order", "create",
                [order_vals]
            )

            if isinstance(order, int):
                order_id = order
            elif isinstance(order, list):
                order_id = order[0]
            else:
                raise ValueError(f"Unexpected return from sale.order.create: {order}")

            order_id = int(order_id)
            logger.info(f"[ORDERS] Sale Order created ID={order_id}")

            # =====================================================
            # Confirm Sale Order (Odoo MAY override date_order here)
            # =====================================================
            self.models.execute_kw(
                self.db, self.uid, self.password,
                "sale.order", "action_confirm",
                [[order_id]]
            )
            logger.info(f"[ORDERS] Sale Order confirmed ID={order_id}")

            # =====================================================
            # CRITICAL FIX:
            # Re-apply date_order AFTER confirm
            # =====================================================
            self.models.execute_kw(
                self.db, self.uid, self.password,
                "sale.order", "write",
                [[order_id], {"date_order": accounting_dt}]
            )
            logger.info(f"[DATE] SO date_order re-applied after confirm: {accounting_dt}")

            # =====================================================
            # Validation: read back date_order
            # =====================================================
            so_data = self.safe_execute_kw(
                "sale.order",
                "read",
                [[order_id]],
                {"fields": ["date_order"]}
            )

            if so_data:
                logger.info(
                    f"[DATE] SO date_order FINAL persisted as: {so_data[0].get('date_order')}"
                )

            return order_id

        except Exception as e:
            logger.error(f"[ORDERS] Error creating sale order: {e}", exc_info=True)
            return None


    # =========================================================
    def validate_delivery_order(self, order_name: str) -> bool:
        """
        Automatically validate delivery order created for this sale order (idempotent).
        
        Args:
            order_name: Sale order name to find delivery order for
        
        Returns:
            True if delivery order validated, False otherwise.
        """
        try:
            pickings = self.safe_execute_kw(
                "stock.picking", "search_read",
                [[["origin", "=", order_name]]],
                {"fields": ["id", "state"], "limit": 1}
            )
            if not pickings or not isinstance(pickings, list) or len(pickings) == 0:
                logger.warning(f"Delivery order not found for order {order_name}")
                return False

            picking_id = pickings[0]["id"]
            state = pickings[0].get("state", "")
            logger.debug(f"Found delivery order (ID={picking_id}) | Current state: {state}")

            if state in ("assigned", "confirmed", "waiting", "ready"):
                self.models.execute_kw(
                    self.db, self.uid, self.password,
                    "stock.picking", "button_validate",
                    [[picking_id]]
                )
                logger.info(f"Validated delivery order (ID={picking_id})")
                return True
            else:
                logger.debug(f"Delivery order not validated - current state: {state}")
                return False
        except Exception as e:
            logger.error(f"Error validating delivery order: {e}", exc_info=True)
            return False
    def normalize_order_id(self, raw_id: str) -> str:
        
        if not raw_id:
            return raw_id

        clean = raw_id.strip().replace("AMZ-", "").replace("AMZ", "").replace(" ", "")

        # Already correct format
        if clean.count("-") == 2:
            return clean

        # Attempt pattern reconstruction
        if len(clean) >= 17 and clean.isdigit():
            return f"{clean[:3]}-{clean[3:10]}-{clean[10:]}"

        return clean
   
