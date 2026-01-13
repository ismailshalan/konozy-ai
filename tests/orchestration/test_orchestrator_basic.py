"""Tests for Orchestrator - basic functionality."""

from datetime import datetime, timezone

import pytest

from app.commands.execution_commands import RecordExecutionCommand
from app.dto.execution_dto import ExecutionDTO
from core.domain.enums.execution_status import ExecutionStatus
from core.domain.value_objects.execution_id import ExecutionID
from orchestration.models import ExecutionContext
from orchestration.orchestrator import Orchestrator
from orchestration.workflow import RetryPolicy, WorkflowDefinition, WorkflowStep


class FakeExecutionService:
    """Fake ExecutionService for testing."""

    def __init__(self) -> None:
        """Initialize fake service."""
        self.last_command: RecordExecutionCommand | None = None

    async def record_execution(self, command: RecordExecutionCommand) -> ExecutionDTO:
        """Record execution and store command."""
        self.last_command = command
        status = ExecutionStatus(command.status)
        finished_at = command.finished_at or datetime.now(timezone.utc)
        return ExecutionDTO.from_execution_id(
            id=1,
            execution_id=command.execution_id,
            service=command.service,
            operation=command.operation,
            status=status,
            created_at=command.started_at,
            updated_at=finished_at,
        )


class FakeEventBus:
    """Fake EventBus for testing."""

    def __init__(self) -> None:
        """Initialize fake event bus."""
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        """Store event."""
        self.events.append(event)

    def subscribe(self, event_name: str, handler: object) -> None:
        """Subscribe handler (no-op for fake)."""
        pass


@pytest.mark.asyncio
async def test_orchestrator_basic_success():
    """Test basic orchestrator workflow success."""
    fake_execution_service = FakeExecutionService()
    fake_event_bus = FakeEventBus()

    # Define simple activity
    async def step_1(ctx: ExecutionContext, input_: object | None) -> str:
        return "ok"

    # Build workflow
    workflow = WorkflowDefinition(
        name="test_workflow",
        service="test",
        operation="simple",
        steps=[
            WorkflowStep(
                name="step_1",
                activity=step_1,
                retry_policy=RetryPolicy(max_attempts=1),
            )
        ],
    )

    # Create orchestrator
    orchestrator = Orchestrator(
        execution_service=fake_execution_service,
        event_bus=fake_event_bus,
        service="test",
        operation="simple",
    )

    # Run workflow
    result = await orchestrator.run(workflow, None)

    # Verify result
    assert result.status == ExecutionStatus.SUCCESS
    assert len(result.steps) == 1
    assert result.steps[0].success is True
    assert result.steps[0].name == "step_1"
    assert result.steps[0].output == "ok"
    assert result.steps[0].attempts == 1

    # Verify execution was recorded
    assert fake_execution_service.last_command is not None
    assert fake_execution_service.last_command.service == "test"
    assert fake_execution_service.last_command.operation == "simple"
    assert fake_execution_service.last_command.status == "success"
    assert fake_execution_service.last_command.execution_id is not None
    assert fake_execution_service.last_command.started_at is not None
    assert fake_execution_service.last_command.finished_at is not None

    # Verify events were published
    assert len(fake_event_bus.events) >= 3  # started, step.started, step.succeeded, finished
    event_names = [event.name for event in fake_event_bus.events]
    assert "workflow.started" in event_names
    assert "workflow.finished" in event_names


@pytest.mark.asyncio
async def test_orchestrator_multiple_steps():
    """Test orchestrator with multiple steps."""
    fake_execution_service = FakeExecutionService()
    fake_event_bus = FakeEventBus()

    async def step_1(ctx: ExecutionContext, input_: object | None) -> str:
        return "step1_result"

    async def step_2(ctx: ExecutionContext, input_: object | None) -> str:
        assert input_ == "step1_result"
        return "step2_result"

    workflow = WorkflowDefinition(
        name="test_workflow",
        service="test",
        operation="multi_step",
        steps=[
            WorkflowStep(name="step_1", activity=step_1),
            WorkflowStep(name="step_2", activity=step_2),
        ],
    )

    orchestrator = Orchestrator(
        execution_service=fake_execution_service,
        event_bus=fake_event_bus,
        service="test",
        operation="multi_step",
    )

    result = await orchestrator.run(workflow, None)

    assert result.status == ExecutionStatus.SUCCESS
    assert len(result.steps) == 2
    assert result.steps[0].success is True
    assert result.steps[1].success is True
    assert result.steps[0].output == "step1_result"
    assert result.steps[1].output == "step2_result"
