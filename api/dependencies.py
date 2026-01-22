"""
FastAPI Dependencies.

Provides dependency injection for use cases and services.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from dotenv import load_dotenv

# Load environment variables ONCE before any settings objects are created
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

from core.settings import get_app_settings

# Mock implementations (replace with real ones later)
from core.infrastructure.adapters.persistence.mock_order_repository import MockOrderRepository
from core.infrastructure.adapters.notifications.mock_notification_service import MockNotificationService
from core.infrastructure.event_bus import get_event_bus
from core.infrastructure.database.config import get_session_factory

if TYPE_CHECKING:
    from core.application.use_cases.sync_amazon_order import SyncAmazonOrderUseCase
    from core.application.services.amazon_sync_service import AmazonSyncService
    from konozy_sdk.amazon import AmazonAPI

logger = logging.getLogger(__name__)


# =============================================================================
# SINGLETON INSTANCES (for demo/testing)
# =============================================================================

_order_repository = None
_odoo_client = None
_notification_service = None
_sync_order_use_case = None
_amazon_sync_service = None
_amazon_order_client = None


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_order_repository():
    global _order_repository
    if _order_repository is None:
        _order_repository = MockOrderRepository()
        logger.info("Created MockOrderRepository instance")
    return _order_repository


def get_odoo_client():
    global _odoo_client
    if _odoo_client is None:
        from apps.adapters.odoo.client import OdooClient
        _odoo_client = OdooClient()
        logger.info(f"Using REAL Odoo XML-RPC client: {_odoo_client}")
    return _odoo_client


def get_notification_service():
    global _notification_service

    if _notification_service is None:
        settings = get_app_settings()

        # Telegram enabled
        if settings.telegram.enabled:
            try:
                from core.infrastructure.adapters.notifications.telegram_notification_service import TelegramNotificationService
                _notification_service = TelegramNotificationService(settings.telegram)
                logger.info("Created TelegramNotificationService instance")
            except Exception as e:
                logger.warning(f"Failed TelegramNotificationService: {e}, fallback to mock")
                _notification_service = MockNotificationService()

        # Slack enabled
        elif settings.slack.enabled:
            try:
                from core.infrastructure.adapters.notifications.slack_notification_service import SlackNotificationService
                _notification_service = SlackNotificationService(settings.slack)
                logger.info("Created SlackNotificationService instance")
            except Exception as e:
                logger.warning(f"Failed SlackNotificationService: {e}, fallback to mock")
                _notification_service = MockNotificationService()

        else:
            _notification_service = MockNotificationService()
            logger.info("Using MockNotificationService (notifications disabled)")

    return _notification_service


def get_sync_order_use_case() -> SyncAmazonOrderUseCase:
    global _sync_order_use_case

    if _sync_order_use_case is None:
        from core.application.use_cases.sync_amazon_order import SyncAmazonOrderUseCase

        _sync_order_use_case = SyncAmazonOrderUseCase(
            order_repository=get_order_repository(),
            odoo_client=get_odoo_client(),
            notification_service=get_notification_service(),
            event_bus=get_event_bus()
        )
        logger.info("Created SyncAmazonOrderUseCase instance")

    return _sync_order_use_case


# =====================================================================
# ⭐⭐ HERE: OVERRIDE SP-API CLIENT TO USE LEGACY CLIENT ⭐⭐
# =====================================================================

def get_amazon_api() -> AmazonAPI:
    """
    Get Amazon SP-API client instance from SDK.
    """
    global _amazon_order_client

    if _amazon_order_client is None:
        from konozy_sdk.amazon import AmazonAPI
        _amazon_order_client = AmazonAPI()
        logger.info("Created AmazonAPI instance from SDK")

    return _amazon_order_client


def get_amazon_sync_service() -> AmazonSyncService:
    global _amazon_sync_service

    if _amazon_sync_service is None:
        from core.application.services.amazon_sync_service import AmazonSyncService
        odoo_client = get_odoo_client()

        _amazon_sync_service = AmazonSyncService(
            sync_order_use_case=get_sync_order_use_case(),
            amazon_order_client=get_amazon_api(),
            odoo_client=odoo_client,
            session_factory=get_session_factory(),
            notification_service=get_notification_service(),
        )
        logger.info("Created AmazonSyncService with REAL Odoo client")

    return _amazon_sync_service


# =============================================================================
# RESET (for testing)
# =============================================================================

def reset_dependencies():
    global _order_repository, _odoo_client, _notification_service
    global _sync_order_use_case, _amazon_sync_service, _amazon_order_client

    _order_repository = None
    _odoo_client = None
    _notification_service = None
    _sync_order_use_case = None
    _amazon_sync_service = None
    _amazon_order_client = None

    logger.info("Dependencies reset")
