"""Tests for Orchestrator - retry functionality."""

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
async def test_orchestrator_retry_success_after_failures():
    """Test orchestrator retry succeeds after initial failures."""
    fake_execution_service = FakeExecutionService()
    fake_event_bus = FakeEventBus()

    counter = {"n": 0}

    async def flaky_step(ctx: ExecutionContext, input_: object | None) -> str:
        counter["n"] += 1
        if counter["n"] < 3:
            raise ValueError("temporary error")
        return "ok"

    workflow = WorkflowDefinition(
        name="test_workflow",
        service="test",
        operation="retry_test",
        steps=[
            WorkflowStep(
                name="flaky_step",
                activity=flaky_step,
                retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
            )
        ],
    )

    orchestrator = Orchestrator(
        execution_service=fake_execution_service,
        event_bus=fake_event_bus,
        service="test",
        operation="retry_test",
    )

    result = await orchestrator.run(workflow, None)

    # Verify retry behavior
    assert counter["n"] == 3
    assert result.status == ExecutionStatus.SUCCESS
    assert len(result.steps) == 1
    assert result.steps[0].success is True
    assert result.steps[0].attempts == 3
    assert result.steps[0].output == "ok"

    # Verify execution was recorded as success
    assert fake_execution_service.last_command is not None
    assert fake_execution_service.last_command.status == "success"


@pytest.mark.asyncio
async def test_orchestrator_retry_fails_after_max_attempts():
    """Test orchestrator fails after max attempts."""
    fake_execution_service = FakeExecutionService()
    fake_event_bus = FakeEventBus()

    counter = {"n": 0}

    async def failing_step(ctx: ExecutionContext, input_: object | None) -> str:
        counter["n"] += 1
        raise ValueError("always fails")

    workflow = WorkflowDefinition(
        name="test_workflow",
        service="test",
        operation="retry_fail_test",
        steps=[
            WorkflowStep(
                name="failing_step",
                activity=failing_step,
                retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.0),
            )
        ],
    )

    orchestrator = Orchestrator(
        execution_service=fake_execution_service,
        event_bus=fake_event_bus,
        service="test",
        operation="retry_fail_test",
    )

    result = await orchestrator.run(workflow, None)

    # Verify failure behavior
    assert counter["n"] == 2  # Max attempts
    assert result.status == ExecutionStatus.FAILED
    assert len(result.steps) == 1
    assert result.steps[0].success is False
    assert result.steps[0].attempts == 2
    assert result.steps[0].error is not None
    assert "always fails" in result.steps[0].error

    # Verify execution was recorded as failed
    assert fake_execution_service.last_command is not None
    assert fake_execution_service.last_command.status == "failed"
