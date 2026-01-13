"""Workflow definitions - Activity, RetryPolicy, WorkflowStep, WorkflowDefinition."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .models import ExecutionContext

# Type alias for workflow activities
Activity = Callable[[ExecutionContext, object | None], Awaitable[object]]


@dataclass
class RetryPolicy:
    """Retry policy for workflow steps."""

    max_attempts: int = 3
    backoff_seconds: float = 0.0


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    name: str
    activity: Activity
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class WorkflowDefinition:
    """Definition of a workflow."""

    name: str
    service: str
    operation: str | None
    steps: list[WorkflowStep]
