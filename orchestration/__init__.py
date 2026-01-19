"""Orchestration layer - workflow orchestration with eventing."""

from typing import TYPE_CHECKING

from .bus import EventBusProtocol, InMemoryEventBus
from .events import Event, EventMetadata
from .models import ExecutionContext, StepResult, WorkflowResult
from .orchestrator import Orchestrator
from .workflow import Activity, RetryPolicy, WorkflowDefinition, WorkflowStep

if TYPE_CHECKING:
    from core.application.services.execution_service import ExecutionService

__all__ = [
    "Activity",
    "Event",
    "EventBusProtocol",
    "EventMetadata",
    "ExecutionContext",
    "InMemoryEventBus",
    "Orchestrator",
    "RetryPolicy",
    "StepResult",
    "WorkflowDefinition",
    "WorkflowResult",
    "WorkflowStep",
]


def create_default_orchestrator(
    execution_service: "ExecutionService", service: str, operation: str | None = None
) -> Orchestrator:
    """Create a default orchestrator with in-memory event bus.

    Args:
        execution_service: ExecutionService instance
        service: Service name
        operation: Optional operation name

    Returns:
        Orchestrator instance
    """
    bus = InMemoryEventBus()
    return Orchestrator(
        execution_service=execution_service,
        event_bus=bus,
        service=service,
        operation=operation,
    )
