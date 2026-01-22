"""
Production-grade Odoo XML-RPC Client.

Implements IOdooClient interface for async Odoo operations.
"""
import logging
import xmlrpc.client
import asyncio
from typing import Any, Dict, List, Optional

from core.application.interfaces import IOdooClient
from core.settings.modules.odoo_settings import OdooSettings


logger = logging.getLogger(__name__)


class OdooClientError(Exception):
    """Generic Odoo client error."""
    pass


class OdooAuthError(OdooClientError):
    """Raised when authentication fails."""
    pass


class OdooCallError(OdooClientError):
    """Raised when an XML-RPC call fails."""
    pass


class OdooClient(IOdooClient):
    """
    Production-grade async Odoo XML-RPC client.
    
    Implements IOdooClient interface using xmlrpc.client with async wrappers.
    Supports automatic reconnection on session expiry.
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        db: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        settings: Optional[OdooSettings] = None,
    ):
        """
        Initialize Odoo XML-RPC client.
        
        Args:
            url: Odoo server URL (optional, uses settings if not provided)
            db: Database name (optional, uses settings if not provided)
            username: Username (optional, uses settings if not provided)
            password: Password (optional, uses settings if not provided)
            settings: OdooSettings instance (optional, creates new if not provided)
        """
        # Load settings
        if settings is None:
            settings = OdooSettings()
        
        self.url = url or settings.url
        self.db = db or settings.db
        self.username = username or settings.username
        self.password = password or settings.password
        
        # Ensure URL doesn't have trailing slash for XML-RPC endpoints
        self.url = self.url.rstrip('/')
        
        if not self.url or not self.db or not self.username or not self.password:
            raise OdooAuthError(
                f"Missing Odoo connection config: "
                f"url={self.url!r}, db={self.db!r}, user={self.username!r}"
            )
        
        # XML-RPC endpoints (will be initialized in authenticate)
        self.common: Optional[xmlrpc.client.ServerProxy] = None
        self.models: Optional[xmlrpc.client.ServerProxy] = None
        self.uid: Optional[int] = None
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info(
            f"OdooClient initialized: url={self.url} db={self.db} user={self.username}"
        )
    
    async def authenticate(self) -> int:
        """
        Authenticate with Odoo and return user ID.
        
        Returns:
            User ID (uid)
            
        Raises:
            OdooAuthError: If authentication fails
        """
        async with self._lock:
            try:
                # Create XML-RPC proxies
                self.common = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/common",
                    allow_none=True
                )
                self.models = xmlrpc.client.ServerProxy(
                    f"{self.url}/xmlrpc/2/object",
                    allow_none=True
                )
                
                # Run synchronous authenticate in executor
                loop = asyncio.get_event_loop()
                uid = await loop.run_in_executor(
                    None,
                    lambda: self.common.authenticate(
                        self.db, self.username, self.password, {}
                    )
                )
                
                if not uid:
                    raise OdooAuthError(
                        f"Odoo authentication returned uid={uid!r} "
                        f"(db={self.db}, user={self.username})"
                    )
                
                self.uid = int(uid)
                logger.info(
                    f"✅ Authenticated with Odoo: uid={self.uid} "
                    f"(url={self.url}, db={self.db}, user={self.username})"
                )
                
                return self.uid
                
            except xmlrpc.client.Fault as fault:
                logger.error(f"Odoo XML-RPC Fault during authentication: {fault}")
                raise OdooAuthError(f"Authentication failed: {fault}") from fault
            except Exception as exc:
                logger.exception("Failed to authenticate with Odoo via XML-RPC")
                raise OdooAuthError(f"Failed to authenticate with Odoo: {exc}") from exc
    
    async def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated, re-authenticate if needed."""
        if self.uid is None or self.common is None or self.models is None:
            await self.authenticate()
    
    async def _execute_kw(
        self,
        model: str,
        method: str,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        retry_on_auth_error: bool = True,
    ) -> Any:
        """
        Execute Odoo XML-RPC method with error handling and retry.
        
        Args:
            model: Odoo model name
            method: Method name
            args: Positional arguments
            kwargs: Keyword arguments
            retry_on_auth_error: Whether to retry on auth error
            
        Returns:
            Method result
            
        Raises:
            OdooCallError: If call fails
        """
        await self._ensure_authenticated()
        
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.models.execute_kw(
                    self.db,
                    self.uid,
                    self.password,
                    model,
                    method,
                    list(args),
                    kwargs,
                )
            )
            
            logger.debug(
                f"[ODOO] {model}.{method}(args={args}, kwargs={kwargs}) → {str(result)[:200]}"
            )
            
            return result
            
        except xmlrpc.client.Fault as fault:
            # Check if it's an authentication error
            fault_str = str(fault).lower()
            if ("session" in fault_str or "authentication" in fault_str or 
                "access denied" in fault_str) and retry_on_auth_error:
                logger.warning(f"Session expired, re-authenticating: {fault}")
                # Reset authentication
                self.uid = None
                await self.authenticate()
                # Retry once
                return await self._execute_kw(model, method, args, kwargs, retry_on_auth_error=False)
            
            logger.error(f"[ODOO] Fault in {model}.{method}: {fault}", exc_info=True)
            raise OdooCallError(f"Odoo Fault in {model}.{method}: {fault}") from fault
            
        except Exception as exc:
            logger.error(f"[ODOO] Error in {model}.{method}: {exc}", exc_info=True)
            raise OdooCallError(f"Odoo error in {model}.{method}: {exc}") from exc
    
    async def get_partner_by_email(self, email: str) -> Optional[int]:
        """
        Get Odoo partner ID by email.
        
        Args:
            email: Partner email address
            
        Returns:
            Partner ID if found, None otherwise
        """
        try:
            logger.debug(f"Searching for partner with email: {email}")
            
            partner_ids = await self._execute_kw(
                "res.partner",
                "search",
                [[["email", "=", email]]],
                {"limit": 1}
            )
            
            if partner_ids:
                partner_id = int(partner_ids[0])
                logger.info(f"✅ Found partner by email {email}: {partner_id}")
                return partner_id
            
            logger.info(f"❌ No partner found for email: {email}")
            return None
            
        except Exception as e:
            logger.error(f"Error looking up partner by email {email}: {e}", exc_info=True)
            return None
    
    async def create_invoice(
        self,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]]
    ) -> int:
        """
        Create invoice in Odoo.
        
        Args:
            header: Invoice header data (partner_id, move_type, invoice_date, ref, etc.)
            lines: List of invoice line dicts
            
        Returns:
            Created invoice ID
            
        Raises:
            OdooCallError: If invoice creation fails
        """
        try:
            logger.info(
                f"Creating invoice in Odoo: partner_id={header.get('partner_id')}, "
                f"ref={header.get('ref')}, lines={len(lines)}"
            )
            
            # Convert lines to Odoo format: [(0, 0, {...}), ...]
            invoice_lines = [
                (0, 0, {
                    "product_id": line.get("product_id"),
                    "name": line.get("name", ""),
                    "quantity": line.get("quantity", 1.0),
                    "price_unit": line.get("price_unit", 0.0),
                    "account_id": line.get("account_id"),
                    "tax_ids": line.get("tax_ids", [(6, 0, [])]),
                })
                for line in lines
            ]
            
            # Prepare invoice values
            invoice_vals: Dict[str, Any] = {
                "move_type": header.get("move_type", "out_invoice"),
                "partner_id": header.get("partner_id"),
                "invoice_line_ids": invoice_lines,
            }
            
            # Add optional fields
            if "invoice_date" in header:
                invoice_vals["invoice_date"] = header["invoice_date"]
            if "ref" in header:
                invoice_vals["ref"] = header["ref"]
            if "journal_id" in header:
                invoice_vals["journal_id"] = header["journal_id"]
            if "date" in header:
                invoice_vals["date"] = header["date"]
            
            # Create invoice
            invoice_id = await self._execute_kw(
                "account.move",
                "create",
                [[invoice_vals]]
            )
            
            invoice_id_int = int(invoice_id) if isinstance(invoice_id, (list, tuple)) else int(invoice_id)
            
            logger.info(
                f"✅ Invoice created successfully in Odoo: id={invoice_id_int}, "
                f"partner_id={header.get('partner_id')}, ref={header.get('ref')}"
            )
            
            return invoice_id_int
            
        except OdooCallError:
            raise
        except Exception as e:
            logger.error(f"Error creating invoice in Odoo: {e}", exc_info=True)
            raise OdooCallError(f"Failed to create invoice: {e}") from e
    
    async def search(
        self,
        model: str,
        domain: List[Any],
        limit: Optional[int] = None
    ) -> List[int]:
        """
        Generic search method.
        
        Args:
            model: Odoo model name
            domain: Search domain
            limit: Optional limit
            
        Returns:
            List of record IDs
        """
        kwargs: Dict[str, Any] = {}
        if limit is not None:
            kwargs["limit"] = limit
        
        logger.debug(f"[XMLRPC] search: model={model}, domain={domain}, kwargs={kwargs}")
        return await self._execute_kw(model, "search", [domain], kwargs)
    
    async def read(
        self,
        model: str,
        ids: List[int],
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generic read method.
        
        Args:
            model: Odoo model name
            ids: List of record IDs
            fields: Optional list of fields to read
            
        Returns:
            List of record dictionaries
        """
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        
        return await self._execute_kw(model, "read", [[ids]], kwargs)
    
    async def create(
        self,
        model: str,
        data: Dict[str, Any]
    ) -> int:
        """
        Generic create method.
        
        Args:
            model: Odoo model name
            data: Record data dictionary
            
        Returns:
            Created record ID
        """
        result = await self._execute_kw(model, "create", [[data]])
        return int(result) if isinstance(result, (list, tuple)) else int(result)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<OdooClient url={self.url} db={self.db} user={self.username}>"
