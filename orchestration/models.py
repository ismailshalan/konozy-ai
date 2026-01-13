"""Orchestration models - ExecutionContext, StepResult, WorkflowResult."""

from dataclasses import dataclass, field
from datetime import datetime

from core.domain.enums.execution_status import ExecutionStatus
from core.domain.value_objects.execution_id import ExecutionID


@dataclass
class ExecutionContext:
    """Context object for workflow execution."""

    execution_id: ExecutionID
    service: str
    operation: str | None
    started_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    name: str
    success: bool
    attempts: int
    duration_ms: int
    error: str | None = None
    output: object = None


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    execution_id: ExecutionID
    service: str
    operation: str | None
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime
    steps: list[StepResult]
