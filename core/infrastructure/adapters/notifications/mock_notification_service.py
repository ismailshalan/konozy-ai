"""
Mock Notification Service Implementation.

This simulates notifications for testing and demos.
"""
from typing import Optional
import logging

from core.domain.value_objects import ExecutionID
from core.application.interfaces import INotificationService


logger = logging.getLogger(__name__)


class MockNotificationService(INotificationService):
    """
    Mock implementation of notification service.
    
    Logs notifications instead of actually sending them.
    Useful for testing and demos.
    """
    
    def __init__(self):
        """Initialize mock notification service."""
        self.notifications_sent = []
        logger.info("MockNotificationService initialized (console logging)")
    
    async def send_success(
        self,
        execution_id: ExecutionID,
        order_id: str,
        odoo_invoice_id: Optional[int],
        message: str
    ) -> None:
        """
        Simulate success notification.
        
        Args:
            execution_id: Execution ID
            order_id: Order ID
            odoo_invoice_id: Invoice ID
            message: Success message
        """
        notification = {
            "type": "success",
            "execution_id": str(execution_id.value),
            "order_id": order_id,
            "invoice_id": odoo_invoice_id,
            "message": message
        }
        
        self.notifications_sent.append(notification)
        
        logger.info(
            f"✅ 🔔 SUCCESS NOTIFICATION:\n"
            f"   Execution: {execution_id.value}\n"
            f"   Order: {order_id}\n"
            f"   Invoice: {odoo_invoice_id}\n"
            f"   Message: {message}"
        )
    
    async def send_error(
        self,
        execution_id: ExecutionID,
        order_id: str,
        error: str,
        details: Optional[str]
    ) -> None:
        """
        Simulate error notification.
        
        Args:
            execution_id: Execution ID
            order_id: Order ID
            error: Error message
            details: Error details
        """
        notification = {
            "type": "error",
            "execution_id": str(execution_id.value),
            "order_id": order_id,
            "error": error,
            "details": details
        }
        
        self.notifications_sent.append(notification)
        
        logger.error(
            f"❌ 🔔 ERROR NOTIFICATION:\n"
            f"   Execution: {execution_id.value}\n"
            f"   Order: {order_id}\n"
            f"   Error: {error}\n"
            f"   Details: {details}"
        )
    
    async def send_batch_summary(
        self,
        total: int,
        successful: int,
        failed: int,
        execution_ids: list
    ) -> bool:
        """
        Simulate batch summary notification.
        
        Args:
            total: Total orders
            successful: Successful count
            failed: Failed count
            execution_ids: List of execution IDs
        
        Returns:
            Always True
        """
        notification = {
            "type": "batch_summary",
            "total": total,
            "successful": successful,
            "failed": failed,
            "execution_ids": execution_ids
        }
        
        self.notifications_sent.append(notification)
        
        logger.info(
            f"📊 🔔 BATCH SUMMARY:\n"
            f"   Total: {total}\n"
            f"   Successful: {successful}\n"
            f"   Failed: {failed}\n"
            f"   Success Rate: {(successful/total*100):.1f}%"
        )
        
        return True
    
    def get_notifications(self) -> list:
        """Get all sent notifications (for testing)."""
        return self.notifications_sent
    
    async def notify(self, message: str, severity: int = 50) -> None:
        """
        Send a generic notification message.
        
        Args:
            message: Notification message
            severity: Severity level (0-100, higher = more critical)
        """
        notification = {
            "type": "generic",
            "message": message,
            "severity": severity,
        }
        
        self.notifications_sent.append(notification)
        
        severity_emoji = "🔴" if severity >= 80 else "🟡" if severity >= 50 else "🟢"
        logger.info(
            f"{severity_emoji} 🔔 NOTIFICATION (severity={severity}):\n"
            f"   {message}"
        )
    
    def clear(self) -> None:
        """Clear notifications (for testing)."""
        self.notifications_sent.clear()
        logger.info("🗑️ Notifications cleared")
