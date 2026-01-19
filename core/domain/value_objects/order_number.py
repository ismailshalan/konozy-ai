"""Order number value object."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderNumber:
    """
    Amazon order identifier.
    
    Format: XXX-XXXXXXX-XXXXXXX (3-7-7 digits with hyphens)
    Examples:
    - 171-3372061-4556310
    - 407-1263947-9146736
    - 408-8327146-7101142
    """
    value: str
    
    def __post_init__(self):
        if not self.value:
            raise ValueError("Order number cannot be empty")
        
        # First character must be a digit
        if not self.value[0].isdigit():
            raise ValueError(
                f"Order number must start with a digit: {self.value}"
            )
        
        # Validate format: XXX-XXXXXXX-XXXXXXX
        parts = self.value.split('-')
        if len(parts) != 3:
            raise ValueError(
                f"Invalid Amazon order format (expected 3 parts): {self.value}"
            )
        
        # All parts should be numeric
        if not all(part.isdigit() for part in parts):
            raise ValueError(
                f"Invalid Amazon order format (non-numeric parts): {self.value}"
            )
        
        # Validate part lengths (typical Amazon format)
        if not (3 <= len(parts[0]) <= 3 and 
                6 <= len(parts[1]) <= 8 and 
                6 <= len(parts[2]) <= 8):
            # Note: This is a soft validation - log warning but don't fail
            import logging
            logging.warning(
                f"Unusual Amazon order format: {self.value} "
                f"(expected XXX-XXXXXXX-XXXXXXX)"
            )
    
    def __str__(self) -> str:
        return self.value
