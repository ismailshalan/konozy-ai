"""
Slack Notification Service Implementation.

Sends notifications via Slack Webhook API.
"""
from typing import Optional
import logging
import aiohttp

from core.domain.value_objects import ExecutionID
from core.application.interfaces import INotificationService
from core.settings.modules.integrations_settings import SlackSettings


logger = logging.getLogger(__name__)


class SlackNotificationService(INotificationService):
    """
    Slack implementation of notification service.
    
    Sends notifications via Slack Webhook API.
    """
    
    def __init__(self, settings: SlackSettings):
        """
        Initialize Slack notification service.
        
        Args:
            settings: Slack settings with webhook URL
        """
        self.settings = settings
        self.webhook_url = settings.webhook_url
        self.prefix = settings.prefix
        logger.info("SlackNotificationService initialized")
    
    async def send_success(
        self,
        execution_id: ExecutionID,
        order_id: str,
        odoo_invoice_id: Optional[int],
        message: str
    ) -> None:
        """Send success notification via Slack."""
        text = (
            f"✅ *Success*\n"
            f"Execution: `{execution_id.value}`\n"
            f"Order: `{order_id}`\n"
            f"Invoice: `{odoo_invoice_id}`\n"
            f"Message: {message}"
        )
        await self._send_message(text, color="good")
    
    async def send_error(
        self,
        execution_id: ExecutionID,
        order_id: str,
        error: str,
        details: Optional[str]
    ) -> None:
        """Send error notification via Slack."""
        text = (
            f"❌ *Error*\n"
            f"Execution: `{execution_id.value}`\n"
            f"Order: `{order_id}`\n"
            f"Error: {error}\n"
        )
        if details:
            text += f"Details: {details}"
        await self._send_message(text, color="danger")
    
    async def notify(self, message: str, severity: int = 50) -> None:
        """
        Send a generic notification message.
        
        Args:
            message: Notification message
            severity: Severity level (0-100, higher = more critical)
        """
        color = "danger" if severity >= 80 else "warning" if severity >= 50 else "good"
        prefixed_message = f"{self.prefix} {message}"
        await self._send_message(prefixed_message, color=color)
    
    async def _send_message(self, text: str, color: str = "good") -> None:
        """
        Send message to Slack.
        
        Args:
            text: Message text
            color: Attachment color (good, warning, danger)
        """
        if not self.webhook_url:
            logger.warning("Slack webhook_url not configured, skipping notification")
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "attachments": [
                        {
                            "color": color,
                            "text": text,
                            "mrkdwn_in": ["text"],
                        }
                    ]
                }
                
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Slack API error: {response.status} - {error_text}"
                        )
                    else:
                        logger.info("Slack notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}", exc_info=True)
