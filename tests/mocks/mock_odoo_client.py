"""
Mock Odoo Client Implementation.

This simulates Odoo integration for testing and demos.
Moved from core/infrastructure/adapters/odoo/mock_odoo_client.py
"""
from typing import Dict, List, Any, Optional
import logging
import asyncio

from core.application.interfaces import IOdooClient


logger = logging.getLogger(__name__)


class MockOdooClient(IOdooClient):
    """
    Mock implementation of Odoo client.
    
    Simulates Odoo operations without actual connection.
    Useful for testing and demos.
    """
    
    def __init__(self):
        """Initialize mock client."""
        self._invoice_counter = 1000
        self._partners = {
            "test@example.com": 123,
            "buyer@amazon.com": 456,
        }
        self._products = {
            "JR-ZS283": 789,
            "jr_PBF17 __Black": 790,
        }
        logger.info("MockOdooClient initialized (no real Odoo connection)")
    
    async def create_invoice(
        self,
        header: Dict[str, Any],
        lines: List[Dict[str, Any]]
    ) -> int:
        """
        Simulate invoice creation in Odoo.
        
        Args:
            header: Invoice header
            lines: Invoice lines
        
        Returns:
            Mock invoice ID
        """
        invoice_id = self._invoice_counter
        self._invoice_counter += 1
        
        logger.info(
            f"📝 Mock Odoo: Creating invoice #{invoice_id}"
        )
        logger.info(
            f"   Header: journal={header.get('journal_id')}, "
            f"partner={header.get('partner_id')}, "
            f"ref={header.get('ref')}"
        )
        logger.info(
            f"   Lines: {len(lines)} line(s)"
        )
        
        # Log each line
        for i, line in enumerate(lines, 1):
            logger.info(
                f"   Line {i}: {line.get('name')} - "
                f"Amount: {line.get('price_unit')} - "
                f"Account: {line.get('account_id')}"
            )
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        logger.info(f"✅ Mock Odoo: Invoice #{invoice_id} created successfully!")
        
        return invoice_id
    
    async def get_partner_by_email(
        self,
        email: str
    ) -> Optional[int]:
        """
        Simulate partner lookup by email.
        
        Args:
            email: Partner email
        
        Returns:
            Partner ID if found, None otherwise
        """
        partner_id = self._partners.get(email)
        
        if partner_id:
            logger.info(f"✅ Mock Odoo: Partner found for {email}: {partner_id}")
        else:
            logger.info(f"❌ Mock Odoo: No partner found for {email}")
        
        return partner_id
    
    async def get_product_by_sku(
        self,
        sku: str
    ) -> Optional[int]:
        """
        Simulate product lookup by SKU.
        
        Args:
            sku: Product SKU
        
        Returns:
            Product ID if found, None otherwise
        """
        product_id = self._products.get(sku)
        
        if product_id:
            logger.info(f"✅ Mock Odoo: Product found for SKU {sku}: {product_id}")
        else:
            logger.info(f"❌ Mock Odoo: No product found for SKU {sku}")
        
        return product_id
    
    async def validate_invoice(
        self,
        invoice_id: int
    ) -> bool:
        """
        Simulate invoice validation (posting).
        
        Args:
            invoice_id: Invoice ID to validate
        
        Returns:
            Always True (success)
        """
        logger.info(f"✅ Mock Odoo: Invoice #{invoice_id} validated (posted)")
        return True
    
    def add_partner(self, email: str, partner_id: int) -> None:
        """Add partner for testing."""
        self._partners[email] = partner_id
        logger.info(f"Added mock partner: {email} → {partner_id}")
    
    def add_product(self, sku: str, product_id: int) -> None:
        """Add product for testing."""
        self._products[sku] = product_id
        logger.info(f"Added mock product: {sku} → {product_id}")
