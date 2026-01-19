"""
Execution Status Enum.

Status values for execution tracking.
"""
from enum import Enum


class ExecutionStatus(str, Enum):
    """Execution status values."""
    
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    RUNNING = "running"
    CANCELLED = "cancelled"
