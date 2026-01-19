"""
SQLAlchemy Order Repository Implementation.

Implements OrderRepository interface using SQLAlchemy and PostgreSQL.
"""
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import logging
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.domain.entities import Order
from core.domain.value_objects import OrderNumber, ExecutionID, Money, FinancialBreakdown, FinancialLine
from core.domain.repositories import OrderRepository
from core.infrastructure.database.models import OrderModel, OrderItemModel, FinancialLineModel


logger = logging.getLogger(__name__)


class SQLAlchemyOrderRepository(OrderRepository):
    """
    SQLAlchemy implementation of OrderRepository.
    
    Handles persistence of Order entities using PostgreSQL.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def save(self, order: Order, execution_id: ExecutionID) -> None:
        """
        Save or update order in database.
        
        Args:
            order: Order entity to persist
            execution_id: ExecutionID for tracing
        """
        logger.info(f"Saving order: {order.order_id.value}")
        
        # Set execution_id on order if not already set
        if not order.execution_id:
            order.execution_id = execution_id
        
        # Check if order already exists
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.order_id == order.order_id.value)
        )
        existing_order = result.scalar_one_or_none()
        
        if existing_order:
            # Update existing order
            await self._update_order(existing_order, order)
            logger.info(f"✅ Updated order: {order.order_id.value}")
        else:
            # Create new order
            await self._create_order(order)
            logger.info(f"✅ Created order: {order.order_id.value}")
        
        # Note: Commit is handled by Unit of Work
    
    async def find_by_id(self, order_id: OrderNumber) -> Optional[Order]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID to lookup
        
        Returns:
            Order entity if found, None otherwise
        """
        logger.info(f"Getting order: {order_id.value}")
        
        # Query with eager loading of relationships
        result = await self.session.execute(
            select(OrderModel)
            .options(
                selectinload(OrderModel.items),
                selectinload(OrderModel.financial_lines)
            )
            .where(
                and_(
                    OrderModel.order_id == order_id.value,
                    OrderModel.is_deleted == False
                )
            )
        )
        
        order_model = result.scalar_one_or_none()
        
        if not order_model:
            logger.info(f"Order not found: {order_id.value}")
            return None
        
        # Convert to domain entity
        order = self._to_domain_entity(order_model)
        
        logger.info(f"✅ Found order: {order_id.value}")
        return order
    
    async def find_all(self, limit: int = 100) -> List[Order]:
        """
        List orders with pagination.
        
        Args:
            limit: Maximum number of orders to return
        
        Returns:
            List of Order aggregates
        """
        return await self.find_all_async(limit=limit, offset=0)
    
    async def exists(self, order_id: OrderNumber) -> bool:
        """
        Check if order already exists.
        
        Args:
            order_id: Order ID to check
        
        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(OrderModel).where(
                and_(
                    OrderModel.order_id == order_id.value,
                    OrderModel.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def delete(self, order_id: OrderNumber) -> None:
        """
        Soft delete order.
        
        Args:
            order_id: Order ID to delete
        """
        logger.info(f"Deleting order: {order_id.value}")
        
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.order_id == order_id.value)
        )
        
        order_model = result.scalar_one_or_none()
        
        if order_model:
            # Soft delete
            order_model.is_deleted = True
            order_model.deleted_at = datetime.utcnow()
            logger.info(f"✅ Deleted order: {order_id.value}")
        else:
            logger.warning(f"Order not found for deletion: {order_id.value}")
    
    async def find_by_marketplace(
        self,
        marketplace: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Order]:
        """
        Find orders by marketplace.
        
        Args:
            marketplace: Marketplace name (e.g., 'amazon', 'noon')
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of orders
        """
        logger.info(f"Finding orders for marketplace: {marketplace}")
        
        result = await self.session.execute(
            select(OrderModel)
            .options(
                selectinload(OrderModel.items),
                selectinload(OrderModel.financial_lines)
            )
            .where(
                and_(
                    OrderModel.marketplace == marketplace,
                    OrderModel.is_deleted == False
                )
            )
            .order_by(OrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        order_models = result.scalars().all()
        
        orders = [self._to_domain_entity(om) for om in order_models]
        
        logger.info(f"✅ Found {len(orders)} orders for {marketplace}")
        return orders
    
    async def find_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Order]:
        """
        Find orders by status.
        
        Args:
            status: Order status (e.g., 'Pending', 'Synced')
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of orders
        """
        logger.info(f"Finding orders with status: {status}")
        
        result = await self.session.execute(
            select(OrderModel)
            .options(
                selectinload(OrderModel.items),
                selectinload(OrderModel.financial_lines)
            )
            .where(
                and_(
                    OrderModel.order_status == status,
                    OrderModel.is_deleted == False
                )
            )
            .order_by(OrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        order_models = result.scalars().all()
        
        orders = [self._to_domain_entity(om) for om in order_models]
        
        logger.info(f"✅ Found {len(orders)} orders with status {status}")
        return orders
    
    def get_all(self) -> List[Order]:
        """
        Get all orders (synchronous - for compatibility).
        
        Note: This is sync wrapper for async method.
        Use find_all_async() for proper async usage.
        
        Returns:
            List of all orders
        """
        # This is a sync wrapper - not ideal but needed for compatibility
        # In production, use find_all_async() instead
        import asyncio
        return asyncio.run(self.find_all_async())
    
    async def find_all_async(
        self,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Order]:
        """
        Find all orders (async).
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of all orders
        """
        logger.info("Finding all orders")
        
        result = await self.session.execute(
            select(OrderModel)
            .options(
                selectinload(OrderModel.items),
                selectinload(OrderModel.financial_lines)
            )
            .where(OrderModel.is_deleted == False)
            .order_by(OrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        order_models = result.scalars().all()
        
        orders = [self._to_domain_entity(om) for om in order_models]
        
        logger.info(f"✅ Found {len(orders)} orders")
        return orders
    
    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================
    
    async def _create_order(self, order: Order) -> None:
        """Create new order in database."""
        # Create order model
        order_model = OrderModel(
            order_id=order.order_id.value,
            execution_id=order.execution_id.value if order.execution_id else None,
            marketplace=order.marketplace or "unknown",
            purchase_date=order.purchase_date,
            buyer_email=order.buyer_email,
            order_status=order.order_status,
            error_message=order.error_message,
        )
        
        # Add financial data if available
        if order.financial_breakdown:
            breakdown = order.financial_breakdown
            
            order_model.principal_amount = breakdown.principal.amount
            order_model.principal_currency = breakdown.principal.currency
            order_model.net_proceeds_amount = breakdown.net_proceeds.amount
            order_model.net_proceeds_currency = breakdown.net_proceeds.currency
            
            # Store full breakdown as JSON
            order_model.financial_breakdown = self._serialize_financial_breakdown(breakdown)
            
            # Create financial line models
            for line in breakdown.financial_lines:
                line_model = FinancialLineModel(
                    order_id=order_model.id,
                    line_type=line.line_type,
                    description=line.description,
                    amount=line.amount.amount,
                    currency=line.amount.currency,
                    sku=line.sku,
                    odoo_account_id=line.odoo_mapping.account_id if line.odoo_mapping else None,
                    odoo_analytic_id=line.odoo_mapping.analytic_account_id if line.odoo_mapping else None,
                )
                order_model.financial_lines.append(line_model)
        
        # Add order to session
        self.session.add(order_model)
    
    async def _update_order(self, order_model: OrderModel, order: Order) -> None:
        """Update existing order in database."""
        # Update basic fields
        order_model.marketplace = order.marketplace or "unknown"
        order_model.purchase_date = order.purchase_date
        order_model.buyer_email = order.buyer_email
        order_model.order_status = order.order_status
        order_model.error_message = order.error_message
        order_model.updated_at = datetime.utcnow()
        
        # Update execution ID if available
        if order.execution_id:
            order_model.execution_id = order.execution_id.value
        
        # Update financial data if available
        if order.financial_breakdown:
            breakdown = order.financial_breakdown
            
            order_model.principal_amount = breakdown.principal.amount
            order_model.principal_currency = breakdown.principal.currency
            order_model.net_proceeds_amount = breakdown.net_proceeds.amount
            order_model.net_proceeds_currency = breakdown.net_proceeds.currency
            order_model.financial_breakdown = self._serialize_financial_breakdown(breakdown)
            
            # Delete old financial lines
            for line_model in list(order_model.financial_lines):
                await self.session.delete(line_model)
            
            # Create new financial lines
            order_model.financial_lines = []
            for line in breakdown.financial_lines:
                line_model = FinancialLineModel(
                    order_id=order_model.id,
                    line_type=line.line_type,
                    description=line.description,
                    amount=line.amount.amount,
                    currency=line.amount.currency,
                    sku=line.sku,
                    odoo_account_id=line.odoo_mapping.account_id if line.odoo_mapping else None,
                    odoo_analytic_id=line.odoo_mapping.analytic_account_id if line.odoo_mapping else None,
                )
                order_model.financial_lines.append(line_model)
    
    def _to_domain_entity(self, order_model: OrderModel) -> Order:
        """Convert database model to domain entity."""
        # Reconstruct financial breakdown
        financial_breakdown = None
        
        if order_model.principal_amount is not None:
            # Reconstruct financial lines
            from core.domain.value_objects.financial import AmazonFeeType, OdooAccountMapping
            
            financial_lines = []
            for line_model in order_model.financial_lines:
                # Try to reconstruct odoo_mapping if possible
                odoo_mapping = None
                if line_model.odoo_account_id:
                    odoo_mapping = OdooAccountMapping(
                        account_id=line_model.odoo_account_id,
                        analytic_account_id=line_model.odoo_analytic_id
                    )
                
                financial_lines.append(FinancialLine(
                    line_type=line_model.line_type,
                    description=line_model.description,
                    amount=Money(
                        amount=line_model.amount,
                        currency=line_model.currency
                    ),
                    sku=line_model.sku,
                    odoo_mapping=odoo_mapping
                ))
            
            # Create financial breakdown
            financial_breakdown = FinancialBreakdown(
                principal=Money(
                    amount=order_model.principal_amount,
                    currency=order_model.principal_currency
                ),
                financial_lines=financial_lines,
                net_proceeds=Money(
                    amount=order_model.net_proceeds_amount,
                    currency=order_model.net_proceeds_currency
                )
            )
        
        # Reconstruct execution ID
        execution_id = None
        if order_model.execution_id:
            execution_id = ExecutionID(value=order_model.execution_id)
        
        # Create order entity
        order = Order(
            order_id=OrderNumber(value=order_model.order_id),
            purchase_date=order_model.purchase_date,
            buyer_email=order_model.buyer_email,
            financial_breakdown=financial_breakdown,
            execution_id=execution_id,
            marketplace=order_model.marketplace,
            order_status=order_model.order_status,
        )
        
        # Set error message if present
        if order_model.error_message:
            order.error_message = order_model.error_message
        
        return order
    
    def _serialize_financial_breakdown(self, breakdown: FinancialBreakdown) -> dict:
        """Serialize financial breakdown to JSON."""
        return {
            "principal": {
                "amount": str(breakdown.principal.amount),
                "currency": breakdown.principal.currency
            },
            "net_proceeds": {
                "amount": str(breakdown.net_proceeds.amount),
                "currency": breakdown.net_proceeds.currency
            },
            "financial_lines": [
                {
                    "line_type": line.line_type,
                    "description": line.description,
                    "amount": str(line.amount.amount),
                    "currency": line.amount.currency,
                    "sku": line.sku
                }
                for line in breakdown.financial_lines
            ]
        }
