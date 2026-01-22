"""Application layer interfaces."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.domain.value_objects import ExecutionID


class IOdooClient(ABC):
    """
    Interface for Odoo client operations.
    
    This interface defines the contract for Odoo integration,
    allowing the application layer to interact with Odoo
    without depending on specific implementation details.
    """
    
    @abstractmethod
    async def get_partner_by_email(self, email: str) -> Optional[int]:
        """
        Get Odoo partner ID by email.
        
        Args:
            email: Partner email address
        
        Returns:
            Partner ID if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def create_invoice(
        self,
        header: Dict[str, Any],
        lines: list[Dict[str, Any]]
    ) -> int:
        """
        Create invoice in Odoo.
        
        Args:
            header: Invoice header data (partner_id, move_type, invoice_date, ref, etc.)
            lines: List of invoice line dicts
        
        Returns:
            Created invoice ID
        
        Raises:
            Exception: If invoice creation fails
        """
        pass


class INotificationService(ABC):
    """
    Interface for notification service operations.
    
    This interface defines the contract for sending notifications,
    allowing different implementations (email, Slack, webhook, etc.)
    """
    
    @abstractmethod
    async def send_success(
        self,
        execution_id: ExecutionID,
        order_id: str,
        odoo_invoice_id: Optional[int],
        message: str
    ) -> None:
        """
        Send success notification.
        
        Args:
            execution_id: Execution tracking ID
            order_id: Order ID
            odoo_invoice_id: Created Odoo invoice ID (if applicable)
            message: Success message
        """
        pass
    
    @abstractmethod
    async def send_error(
        self,
        execution_id: ExecutionID,
        order_id: str,
        error: str,
        details: Optional[str]
    ) -> None:
        """
        Send error notification.
        
        Args:
            execution_id: Execution tracking ID
            order_id: Order ID
            error: Error message
            details: Optional error details
        """
        pass
    
    async def notify(self, message: str, severity: int = 50) -> None:
        """
        Send a generic notification message.
        
        Args:
            message: Notification message
            severity: Severity level (0-100, higher = more critical)
        """
        # Default implementation - can be overridden
        pass


__all__ = ["IOdooClient", "INotificationService"]
