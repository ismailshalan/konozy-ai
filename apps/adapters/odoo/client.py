from __future__ import annotations

import logging
import xmlrpc.client
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import (
    ODOO_CONN_CFG,
    ACCOUNTING_CFG,
    ANALYTICS_CFG,
    MARKETPLACE_CFG,
)

logger = logging.getLogger(__name__)


# ==============================
# Exceptions
# ==============================


class odoo_client_error(Exception):
    """Generic Odoo adapter error."""


class odoo_auth_error(odoo_client_error):
    """Raised when authentication fails."""


class odoo_call_error(odoo_client_error):
    """Raised when an XML-RPC call fails."""


# ==============================
# Low-level Odoo XML-RPC client
# ==============================


class OdooClient:
    """
    Thin but safe XML-RPC adapter around Odoo.

    - Reads connection info from ODOO_CONN_CFG (env-driven).
    - Exposes safe_execute_kw() as the central execution method.
    - Adds small, clear helpers for common patterns.
    """

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        # Connection config (env → ODOO_CONN_CFG → here)
        self.url = url or ODOO_CONN_CFG.url
        self.db = db or ODOO_CONN_CFG.db
        self.username = username or ODOO_CONN_CFG.username
        self.password = password or ODOO_CONN_CFG.password

        if not self.url or not self.db or not self.username or not self.password:
            raise odoo_auth_error(
                f"Missing Odoo connection config: "
                f"url={self.url!r}, db={self.db!r}, user={self.username!r}"
            )

        # XML-RPC endpoints
        self.common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", allow_none=True
        )
        self.models = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object", allow_none=True
        )

        # Authenticate once on init
        try:
            uid = self.common.authenticate(self.db, self.username, self.password, {})
        except Exception as exc:  # pragma: no cover - network error path
            logger.exception("Failed to authenticate with Odoo via XML-RPC")
            raise odoo_auth_error("Failed to authenticate with Odoo") from exc

        if not uid:
            raise odoo_auth_error(
                f"Odoo authentication returned uid={uid!r} "
                f"(db={self.db}, user={self.username})"
            )

        self.uid: int = int(uid)
        logger.info(
            "Connected to Odoo XML-RPC: url=%s db=%s user=%s uid=%s",
            self.url,
            self.db,
            self.username,
            self.uid,
        )

    # ==============================
    # Core safe_execute_kw wrapper
    # ==============================

    def safe_execute_kw(
        self,
        model: str,
        method: str,
        args: Optional[Sequence[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Central, safe XML-RPC call.

        - Adds logging
        - Wraps xmlrpc.client.Fault into odoo_call_error
        - Keeps signature very close to raw execute_kw
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}

        logger.debug(
            "[ODOO] %s.%s(args=%s, kwargs=%s)", model, method, args, kwargs
        )

        try:
            result = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                method,
                list(args),
                kwargs,
            )
            logger.debug(
                "[ODOO] %s.%s → %s", model, method, str(result)[:300]
            )
            return result
        except xmlrpc.client.Fault as fault:  # pragma: no cover - xmlrpc error
            logger.error(
                "[ODOO] Fault in %s.%s: %s", model, method, fault, exc_info=True
            )
            raise odoo_call_error(
                f"Odoo Fault in {model}.{method}: {fault}"
            ) from fault
        except Exception as exc:  # pragma: no cover - generic error
            logger.error(
                "[ODOO] Error in %s.%s: %s", model, method, exc, exc_info=True
            )
            raise odoo_call_error(
                f"Odoo error in {model}.{method}: {exc}"
            ) from exc

    # ==============================
    # Generic helper methods
    # ==============================

    def ping(self) -> Dict[str, Any]:
        """Return server version info."""
        try:
            ver = self.common.version()
        except Exception as exc:  # pragma: no cover
            raise odoo_call_error(f"Failed to fetch Odoo version: {exc}") from exc
        logger.info("Odoo version: %s", ver)
        return ver

    def search(
        self,
        model: str,
        domain: Sequence[Any],
        limit: Optional[int] = None,
    ) -> List[int]:
        kwargs: Dict[str, Any] = {}
        if limit is not None:
            kwargs["limit"] = limit
        return self.safe_execute_kw(model, "search", [domain], kwargs)

    def search_read(
        self,
        model: str,
        domain: Sequence[Any],
        fields: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = list(fields)
        if limit is not None:
            kwargs["limit"] = limit
        return self.safe_execute_kw(model, "search_read", [domain], kwargs)

    def read(
        self,
        model: str,
        ids: Sequence[int],
        fields: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = list(fields)
        return self.safe_execute_kw(model, "read", [list(ids)], kwargs)

    def create(self, model: str, vals: Dict[str, Any]) -> int:
        res = self.safe_execute_kw(model, "create", [[vals]])
        if isinstance(res, list):
            res = res[0]
        return int(res)

    def write(self, model: str, ids: Sequence[int], vals: Dict[str, Any]) -> bool:
        return bool(self.safe_execute_kw(model, "write", [list(ids), vals]))

    def unlink(self, model: str, ids: Sequence[int]) -> bool:
        return bool(self.safe_execute_kw(model, "unlink", [list(ids)]))

    # ==============================
    # Domain helpers (Amazon / Noon)
    # ==============================

    # ---------- Products ----------

    def find_product(self, sku: str) -> Optional[int]:
        """
        Find product by SKU (default_code) with barcode fallback.

        ARCHITECTURAL GUARANTEE:
        - NO product creation
        - default_code first, then barcode
        - Returns None if not found
        """
        if not sku:
            return None

        # default_code
        result = self.search_read(
            "product.product",
            [["default_code", "=", sku]],
            fields=["id"],
            limit=1,
        )
        if result:
            pid = int(result[0]["id"])
            logger.debug("[PRODUCT] Found by default_code=%s (id=%s)", sku, pid)
            return pid

        # barcode fallback
        result = self.search_read(
            "product.product",
            [["barcode", "=", sku]],
            fields=["id"],
            limit=1,
        )
        if result:
            pid = int(result[0]["id"])
            logger.debug("[PRODUCT] Found by barcode=%s (id=%s)", sku, pid)
            return pid

        logger.info("[PRODUCT] Not found for SKU=%s", sku)
        return None

    # ---------- Partners ----------

    def create_or_find_partner(
        self,
        name: str,
        email: Optional[str] = None,
        order_id: Optional[str] = None,
        shipping_address: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Find or create child partner under AMAZON_PARTNER_ID.

        - Child name is "AMZ-{order_id}" إذا توفر order_id.
        - Idempotent: لو موجود بيرجّع نفس الـ id.
        """
        try:
            parent_id = MARKETPLACE_CFG.amazon_partner_id or 19
            child_name = f"AMZ-{order_id}" if order_id else name

            existing = self.search_read(
                "res.partner",
                [["name", "=", child_name], ["parent_id", "=", parent_id]],
                fields=["id"],
                limit=1,
            )

            if existing:
                partner_id = int(existing[0]["id"])
                logger.info(
                    "Partner already exists: %s (id=%s)", child_name, partner_id
                )
            else:
                created = self.create(
                    "res.partner",
                    {
                        "name": child_name,
                        "email": email or False,
                        "customer_rank": 1,
                        "type": "contact",
                        "parent_id": parent_id,
                        "company_type": "person",
                        "comment": "Auto-created from Amazon order",
                    },
                )
                partner_id = int(created)
                logger.info(
                    "Created new partner: %s (id=%s)", child_name, partner_id
                )

            # Optional shipping child contact
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
                        country = self.search_read(
                            "res.country",
                            [["code", "=", code]],
                            fields=["id"],
                            limit=1,
                        )
                        if country:
                            vals["country_id"] = country[0]["id"]
                    self.create("res.partner", vals)
                    logger.info("Shipping address created for %s", child_name)
                except Exception as exc:  # pragma: no cover
                    logger.error(
                        "Error creating shipping address for %s: %s",
                        child_name,
                        exc,
                        exc_info=True,
                    )

            return partner_id

        except Exception as exc:  # pragma: no cover
            logger.error("Error in create_or_find_partner: %s", exc, exc_info=True)
            return MARKETPLACE_CFG.amazon_partner_id or 19

    # ---------- Sale Orders ----------

    def _resolve_accounting_datetime(
        self,
        financial_lines: Optional[List[Dict[str, Any]]],
        order_date: str,
    ) -> str:
        """
        Simple placeholder resolver.

        في النسخة الحالية:
        - لو فيه financial_lines وفيها PostedDate ممكن نطوّرها لاحقًا.
        - حاليًا نرجّع order_date كما هو.
        """
        return order_date

    def create_sale_order(
        self,
        order_name: str,
        partner_id: int,
        order_lines: List[Tuple[int, float, float]],
        order_date: str,
        warehouse_id: Optional[int] = None,
        buyer_metadata: Optional[Dict[str, Optional[str]]] = None,
        financial_lines: Optional[List[Dict[str, Any]]] = None,
        accounting_dt: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create and confirm sale.order.

        ARCHITECTURAL RULE:
        - date_order MUST come from accounting_dt (PostedDate) أو order_date.
        - Existing Sale Orders are NOT updated (idempotency responsibility is خارج هذا الميثود).
        """

        if not order_date and not accounting_dt:
            raise AssertionError(
                "ARCHITECTURAL VIOLATION: Sale Order must be created with PostedDate"
            )

        try:
            warehouse_id = (
                warehouse_id or MARKETPLACE_CFG.amazon_warehouse_id or 1
            )

            # Resolve accounting datetime
            if accounting_dt:
                logger.info("[DATE] Accounting datetime passed: %s", accounting_dt)
            else:
                accounting_dt = self._resolve_accounting_datetime(
                    financial_lines, order_date
                )
            logger.info(
                "[DATE] Creating Sale Order with accounting_dt=%s", accounting_dt
            )

            order_vals: Dict[str, Any] = {
                "name": order_name,
                "partner_id": partner_id,
                "warehouse_id": warehouse_id,
                "date_order": accounting_dt,
                "order_line": [
                    (0, 0, {"product_id": p, "product_uom_qty": q, "price_unit": u})
                    for p, q, u in order_lines
                ],
            }

            # Buyer metadata → client_order_ref + note
            if buyer_metadata:
                parts: List[str] = []
                if buyer_metadata.get("amazon_order_id"):
                    parts.append(f"Amazon Order: {buyer_metadata['amazon_order_id']}")
                if buyer_metadata.get("buyer_name"):
                    parts.append(f"Buyer: {buyer_metadata['buyer_name']}")
                if buyer_metadata.get("buyer_email"):
                    parts.append(f"Email: {buyer_metadata['buyer_email']}")
                if parts:
                    meta_str = " | ".join(parts)
                    order_vals["client_order_ref"] = meta_str
                    order_vals["note"] = f"Amazon Buyer Info:\n{meta_str}"

            logger.info("[ORDERS] Creating sale.order %s", order_name)
            order_id = self.create("sale.order", order_vals)
            logger.info("[ORDERS] Sale Order created id=%s", order_id)

            # Confirm
            self.safe_execute_kw("sale.order", "action_confirm", [[order_id]])
            logger.info("[ORDERS] Sale Order confirmed id=%s", order_id)

            # Re-apply date_order after confirm (Odoo قد يغيّرها)
            self.safe_execute_kw(
                "sale.order",
                "write",
                [[order_id], {"date_order": accounting_dt}],
            )
            logger.info("[DATE] date_order re-applied: %s", accounting_dt)

            # Read back for logging
            so_data = self.read("sale.order", [order_id], fields=["date_order"])
            if so_data:
                logger.info(
                    "[DATE] SO date_order FINAL = %s",
                    so_data[0].get("date_order"),
                )

            return int(order_id)

        except Exception as exc:  # pragma: no cover
            logger.error("[ORDERS] Error creating sale order: %s", exc, exc_info=True)
            return None

    def validate_delivery_order(self, order_name: str) -> bool:
        """Auto-validate stock.picking created for given sale.order (by origin)."""
        try:
            pickings = self.search_read(
                "stock.picking",
                [["origin", "=", order_name]],
                fields=["id", "state"],
                limit=1,
            )
            if not pickings:
                logger.warning(
                    "Delivery order not found for sale order %s", order_name
                )
                return False

            picking_id = pickings[0]["id"]
            state = pickings[0].get("state", "")
            logger.debug(
                "Found delivery picking id=%s state=%s", picking_id, state
            )

            if state in ("assigned", "confirmed", "waiting", "ready"):
                self.safe_execute_kw(
                    "stock.picking", "button_validate", [[picking_id]]
                )
                logger.info("Validated delivery picking id=%s", picking_id)
                return True

            logger.debug(
                "Delivery picking not validated (state=%s) id=%s", state, picking_id
            )
            return False

        except Exception as exc:  # pragma: no cover
            logger.error(
                "Error validating delivery order for %s: %s",
                order_name,
                exc,
                exc_info=True,
            )
            return False

    # ---------- Invoices / Accounting ----------

    def create_invoice_from_sale_order_wizard(
        self, sale_order_id: int
    ) -> Optional[List[int]]:
        """
        Create invoices from sale.order using sale.advance.payment.inv wizard.

        - Uses advance_payment_method='delivered'
        - Returns list of invoice_ids (typically 1)
        """
        try:
            wizard_id = self.safe_execute_kw(
                "sale.advance.payment.inv",
                "create",
                [[{"advance_payment_method": "delivered"}]],
            )
            if isinstance(wizard_id, list):
                wizard_id = wizard_id[0]
            wizard_id = int(wizard_id)

            self.safe_execute_kw(
                "sale.advance.payment.inv",
                "create_invoices",
                [[wizard_id]],
                {
                    "context": {
                        "active_model": "sale.order",
                        "active_ids": [sale_order_id],
                    }
                },
            )

            so_data = self.read(
                "sale.order", [sale_order_id], fields=["invoice_ids"]
            )
            if not so_data:
                logger.error(
                    "Could not read sale.order %s after invoice wizard", sale_order_id
                )
                return None

            invoice_ids = [int(x) for x in so_data[0].get("invoice_ids", []) or []]
            if not invoice_ids:
                logger.error(
                    "No invoices created from sale.order %s", sale_order_id
                )
                return None

            logger.info(
                "Created %s invoice(s) from sale.order %s: %s",
                len(invoice_ids),
                sale_order_id,
                invoice_ids,
            )
            return invoice_ids

        except Exception as exc:  # pragma: no cover
            logger.error(
                "Failed to create invoices from sale.order %s: %s",
                sale_order_id,
                exc,
                exc_info=True,
            )
            return None

    def find_invoice_by_origin(
        self, origin: str, draft_only: bool = False
    ) -> Optional[int]:
        """Find account.move by invoice_origin."""
        domain: List[Any] = [
            ("move_type", "=", "out_invoice"),
            ("invoice_origin", "=", origin),
        ]
        if draft_only:
            domain.append(("state", "=", "draft"))
        else:
            domain.append(("state", "in", ("draft", "posted")))

        ids = self.search("account.move", domain, limit=1)
        return int(ids[0]) if ids else None

    def clear_invoice_lines(self, invoice_id: int) -> None:
        """
        Remove all invoice_line_ids from an invoice (must be draft).
        """
        data = self.read(
            "account.move", [invoice_id], fields=["invoice_line_ids", "state"]
        )
        if not data:
            logger.warning("[INVOICE] %s not found, cannot clear lines", invoice_id)
            return

        state = data[0].get("state", "draft")
        if state != "draft":
            raise ValueError(
                f"Cannot clear lines from invoice {invoice_id} "
                f"(state={state}, must be draft)"
            )

        line_ids = data[0].get("invoice_line_ids", []) or []
        if not line_ids:
            logger.debug("[INVOICE] %s has no lines to clear", invoice_id)
            return

        self.unlink("account.move.line", line_ids)
        logger.info("[INVOICE] Cleared %s line(s) from invoice %s", len(line_ids), invoice_id)

    def write_invoice_lines(
        self, invoice_id: int, invoice_lines: List[Tuple[int, int, Dict[str, Any]]]
    ) -> None:
        """
        Append invoice_line_ids to draft invoice.

        invoice_lines must be [(0, 0, {...}), ...]
        """
        if not invoice_lines:
            logger.debug(
                "[INVOICE] No invoice lines to write to invoice %s", invoice_id
            )
            return

        data = self.read("account.move", [invoice_id], fields=["state"])
        if not data:
            raise ValueError(f"Invoice {invoice_id} not found")

        state = data[0].get("state", "draft")
        if state != "draft":
            raise ValueError(
                f"Cannot write lines to invoice {invoice_id} "
                f"(state={state}, must be draft)"
            )

        self.safe_execute_kw(
            "account.move",
            "write",
            [[invoice_id], {"invoice_line_ids": invoice_lines}],
        )
        logger.info(
            "[INVOICE] Wrote %s line(s) to invoice %s",
            len(invoice_lines),
            invoice_id,
        )

    def create_accounting_move(
        self,
        invoice_id: int,
        order_name: str,
        financial_events: List[Dict[str, Any]],
    ) -> Optional[int]:
        """
        Create accounting move (journal entry) for Amazon fees and commissions.

        financial_events example:
        [{"type": "Commission", "amount": 15.0},
         {"type": "FBAFees", "amount": 5.0}]
        """
        try:
            if not financial_events:
                logger.warning(
                    "No financial events provided for accounting move %s", order_name
                )
                return None

            move_lines: List[Tuple[int, int, Dict[str, Any]]] = []
            total_debit = 0.0

            for event in financial_events:
                fee_type = str(event.get("type", "")).upper()
                amount = float(event.get("amount", 0.0))
                if not amount:
                    continue

                if "COMMISSION" in fee_type:
                    account_id = ACCOUNTING_CFG.amazon_commissions_id
                    analytic_id = ANALYTICS_CFG.amazon_commissions_analytic_id
                elif "FBA" in fee_type or "PICK" in fee_type or "PACK" in fee_type:
                    account_id = ACCOUNTING_CFG.amazon_fba_pick_pack_fee_id
                    analytic_id = ANALYTICS_CFG.analytic_amazon_shipping_cost_id
                elif "COD" in fee_type:
                    account_id = ACCOUNTING_CFG.amazon_cod_fee_id
                    analytic_id = ANALYTICS_CFG.analytic_amazon_shipping_cost_id
                else:
                    # default → commissions
                    account_id = ACCOUNTING_CFG.amazon_commissions_id
                    analytic_id = ANALYTICS_CFG.amazon_commissions_analytic_id

                move_lines.append(
                    (
                        0,
                        0,
                        {
                            "account_id": account_id,
                            "debit": amount,
                            "credit": 0.0,
                            "name": f"{fee_type} - {order_name}",
                            "analytic_distribution": {str(analytic_id): 100.0},
                        },
                    )
                )
                total_debit += amount

            if not move_lines:
                logger.warning(
                    "No valid move lines for accounting move %s", order_name
                )
                return None

            # Credit line (Amazon receivable)
            move_lines.append(
                (
                    0,
                    0,
                    {
                        "account_id": ACCOUNTING_CFG.amazon_account_id,
                        "debit": 0.0,
                        "credit": total_debit,
                        "name": f"Amazon Fees - {order_name}",
                    },
                )
            )

            # Fetch invoice date as move date
            inv = self.read(
                "account.move", [invoice_id], fields=["invoice_date", "date"]
            )
            move_date = "2025-01-01"
            if inv:
                invoice_date = inv[0].get("invoice_date") or inv[0].get("date")
                if invoice_date:
                    move_date = str(invoice_date)[:10]

            move_vals = {
                "move_type": "entry",
                "journal_id": ACCOUNTING_CFG.amazon_journal_id,
                "ref": f"{order_name} - Fees",
                "date": move_date,
                "line_ids": move_lines,
            }

            move_id = self.create("account.move", move_vals)
            logger.info(
                "Accounting move created id=%s for order %s", move_id, order_name
            )

            self.safe_execute_kw(
                "account.move", "action_post", [[move_id]]
            )
            logger.info("Accounting move posted id=%s", move_id)

            return int(move_id)

        except Exception as exc:  # pragma: no cover
            logger.error("Error creating accounting move: %s", exc, exc_info=True)
            return None

    # ---------- Util ----------

    def normalize_order_id(self, raw_id: str) -> str:
        """
        Normalize Amazon order id into 3-7-7 pattern.

        e.g. "12345678901234567" → "123-4567890-1234567"
        """
        if not raw_id:
            return raw_id

        clean = (
            raw_id.strip()
            .replace("AMZ-", "")
            .replace("AMZ", "")
            .replace(" ", "")
        )

        if clean.count("-") == 2:
            return clean

        if len(clean) >= 17 and clean.isdigit():
            return f"{clean[:3]}-{clean[3:10]}-{clean[10:]}"

        return clean
