"""
Execution Service.

Service for recording execution tracking.
"""
from abc import ABC, abstractmethod

from core.application.commands.execution_commands import RecordExecutionCommand
from core.application.dtos.execution_dto import ExecutionDTO


class ExecutionService(ABC):
    """Abstract execution service."""
    
    @abstractmethod
    async def record_execution(self, command: RecordExecutionCommand) -> ExecutionDTO:
        """
        Record execution.
        
        Args:
            command: Record execution command
        
        Returns:
            Execution DTO
        """
        pass
