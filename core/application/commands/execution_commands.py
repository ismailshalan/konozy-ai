"""
Execution commands.

Commands for recording execution tracking.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.domain.value_objects import ExecutionID


@dataclass
class RecordExecutionCommand:
    """Command to record execution tracking."""
    
    execution_id: ExecutionID
    service: str
    operation: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
