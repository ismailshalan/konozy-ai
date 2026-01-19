"""
FastAPI Dependencies.

Provides dependency injection for use cases and services.
"""
import logging

from core.application.use_cases.sync_amazon_order import SyncAmazonOrderUseCase
from core.application.services.amazon_sync_service import AmazonSyncService

# Mock implementations (replace with real ones later)
from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
from core.infrastructure.adapters.odoo.mock_odoo_client import MockOdooClient
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService
from core.infrastructure.event_bus import get_event_bus


logger = logging.getLogger(__name__)


# =============================================================================
# SINGLETON INSTANCES (for demo/testing)
# =============================================================================

_order_repository = None
_odoo_client = None
_notification_service = None
_sync_order_use_case = None
_amazon_sync_service = None


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_order_repository():
    """
    Get order repository instance.
    
    TODO: Replace with real SQLAlchemy repository.
    """
    global _order_repository
    
    if _order_repository is None:
        _order_repository = MockOrderRepository()
        logger.info("Created MockOrderRepository instance")
    
    return _order_repository


def get_odoo_client():
    """
    Get Odoo client instance.
    
    TODO: Replace with real Odoo XML-RPC client.
    """
    global _odoo_client
    
    if _odoo_client is None:
        _odoo_client = MockOdooClient()
        logger.info("Created MockOdooClient instance")
    
    return _odoo_client


def get_notification_service():
    """
    Get notification service instance.
    
    TODO: Replace with real Telegram/WhatsApp service.
    """
    global _notification_service
    
    if _notification_service is None:
        _notification_service = MockNotificationService()
        logger.info("Created MockNotificationService instance")
    
    return _notification_service


def get_sync_order_use_case() -> SyncAmazonOrderUseCase:
    """
    Get sync order use case instance.
    
    This is the main business logic entry point.
    """
    global _sync_order_use_case
    
    if _sync_order_use_case is None:
        _sync_order_use_case = SyncAmazonOrderUseCase(
            order_repository=get_order_repository(),
            odoo_client=get_odoo_client(),
            notification_service=get_notification_service(),
            event_bus=get_event_bus()
        )
        logger.info("Created SyncAmazonOrderUseCase instance")
    
    return _sync_order_use_case


def get_amazon_sync_service() -> AmazonSyncService:
    """
    Get Amazon sync service instance.
    
    This is the high-level service layer.
    """
    global _amazon_sync_service
    
    if _amazon_sync_service is None:
        _amazon_sync_service = AmazonSyncService(
            sync_order_use_case=get_sync_order_use_case()
        )
        logger.info("Created AmazonSyncService instance")
    
    return _amazon_sync_service


# =============================================================================
# RESET (for testing)
# =============================================================================

def reset_dependencies():
    """Reset all dependencies (for testing)."""
    global _order_repository, _odoo_client, _notification_service
    global _sync_order_use_case, _amazon_sync_service
    
    _order_repository = None
    _odoo_client = None
    _notification_service = None
    _sync_order_use_case = None
    _amazon_sync_service = None
    
    logger.info("Dependencies reset")
