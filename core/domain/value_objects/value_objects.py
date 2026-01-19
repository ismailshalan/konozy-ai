"""Domain value objects - pure Python immutable types."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Money:
    """
    Immutable monetary value with currency.
    
    Supports both positive and negative amounts:
    - Positive: Revenue, charges (e.g., +198.83 for principal)
    - Negative: Fees, expenses (e.g., -21.66 for FBA fee)
    
    CRITICAL: Always use Decimal, never float!
    """
    amount: Decimal
    currency: str = "EGP"
    
    def __post_init__(self):
        # Convert to Decimal if needed
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        
        # Validate currency code (3 letters)
        if not isinstance(self.currency, str) or len(self.currency) != 3:
            raise ValueError(
                f"Currency must be 3-letter ISO code, got: {self.currency}"
            )
    
    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
    
    def __add__(self, other: 'Money') -> 'Money':
        """Add two Money objects (must have same currency)."""
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add different currencies: {self.currency} vs {other.currency}"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)
    
    def __sub__(self, other: 'Money') -> 'Money':
        """Subtract two Money objects (must have same currency)."""
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract different currencies: {self.currency} vs {other.currency}"
            )
        return Money(amount=self.amount - other.amount, currency=self.currency)
    
    def __neg__(self) -> 'Money':
        """Negate the amount (useful for conversions)."""
        return Money(amount=-self.amount, currency=self.currency)
    
    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > 0
    
    def is_negative(self) -> bool:
        """Check if amount is negative."""
        return self.amount < 0
    
    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0
    
    def abs(self) -> 'Money':
        """Return absolute value."""
        return Money(amount=abs(self.amount), currency=self.currency)


@dataclass(frozen=True)
class ExecutionID:
    """Unique identifier for workflow execution tracing."""

    value: UUID

    @classmethod
    def generate(cls) -> "ExecutionID":
        """Generate a new ExecutionID."""
        return cls(value=uuid4())

    def __str__(self) -> str:
        """Return string representation."""
        return str(self.value)


# OrderNumber moved to order_number.py
# Import here for backward compatibility
from .order_number import OrderNumber
