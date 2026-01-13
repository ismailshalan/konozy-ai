"""Domain value objects - pure Python immutable types."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Money:
    """Immutable monetary value with currency."""

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate money amount and currency."""
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be 3-letter ISO code")


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


@dataclass(frozen=True)
class OrderNumber:
    """Amazon order identifier with validation."""

    value: str

    def __post_init__(self) -> None:
        """Validate order number format."""
        if not self.value or not self.value.startswith("1"):
            raise ValueError("Invalid Amazon order number format")
