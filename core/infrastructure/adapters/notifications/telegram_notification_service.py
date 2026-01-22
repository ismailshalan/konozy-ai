"""
Telegram Notification Service Implementation.

Sends notifications via Telegram Bot API.
"""
from typing import Optional
import logging
import aiohttp

from core.domain.value_objects import ExecutionID
from core.application.interfaces import INotificationService
from core.settings.modules.integrations_settings import TelegramSettings


logger = logging.getLogger(__name__)


class TelegramNotificationService(INotificationService):
    """
    Telegram implementation of notification service.
    
    Sends notifications via Telegram Bot API.
    """
    
    def __init__(self, settings: TelegramSettings):
        """
        Initialize Telegram notification service.
        
        Args:
            settings: Telegram settings with bot token and chat ID
        """
        self.settings = settings
        self.bot_token = settings.token
        self.chat_id = settings.chat_id
        self.prefix = settings.prefix
        self.min_severity = settings.min_severity
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        logger.info("TelegramNotificationService initialized")
    
    async def send_success(
        self,
        execution_id: ExecutionID,
        order_id: str,
        odoo_invoice_id: Optional[int],
        message: str
    ) -> None:
        """Send success notification via Telegram."""
        text = (
            f"✅ *Success*\n"
            f"Execution: `{execution_id.value}`\n"
            f"Order: `{order_id}`\n"
            f"Invoice: `{odoo_invoice_id}`\n"
            f"Message: {message}"
        )
        await self._send_message(text)
    
    async def send_error(
        self,
        execution_id: ExecutionID,
        order_id: str,
        error: str,
        details: Optional[str]
    ) -> None:
        """Send error notification via Telegram."""
        text = (
            f"❌ *Error*\n"
            f"Execution: `{execution_id.value}`\n"
            f"Order: `{order_id}`\n"
            f"Error: {error}\n"
        )
        if details:
            text += f"Details: {details}"
        await self._send_message(text)
    
    async def notify(self, message: str, severity: int = 50) -> None:
        """
        Send a generic notification message.
        
        Args:
            message: Notification message
            severity: Severity level (0-100, higher = more critical)
        """
        # Check minimum severity threshold
        if severity < self.min_severity:
            logger.debug(f"Notification severity {severity} below threshold {self.min_severity}, skipping")
            return
        
        emoji = "🔴" if severity >= 80 else "🟡" if severity >= 50 else "🟢"
        text = f"{self.prefix} {emoji} {message}"
        await self._send_message(text)
    
    async def _send_message(self, text: str) -> None:
        """
        Send message to Telegram.
        
        Args:
            text: Message text (supports Markdown)
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot_token or chat_id not configured, skipping notification")
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                }
                
                async with session.post(self.api_url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Telegram API error: {response.status} - {error_text}"
                        )
                    else:
                        logger.info("Telegram notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)
