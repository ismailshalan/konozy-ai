"""
Execution DTO.

Data transfer object for execution tracking.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.domain.enums.execution_status import ExecutionStatus
from core.domain.value_objects import ExecutionID


@dataclass
class ExecutionDTO:
    """DTO for execution tracking."""
    
    id: int
    execution_id: ExecutionID
    service: str
    operation: str
    status: ExecutionStatus
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_execution_id(
        cls,
        id: int,
        execution_id: ExecutionID,
        service: str,
        operation: str,
        status: ExecutionStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> "ExecutionDTO":
        """Create ExecutionDTO from execution ID."""
        return cls(
            id=id,
            execution_id=execution_id,
            service=service,
            operation=operation,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
        )
