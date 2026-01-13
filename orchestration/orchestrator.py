"""Orchestrator - runs workflows with eventing and execution tracking."""

import asyncio

from app.commands.execution_commands import RecordExecutionCommand
from app.services.execution_service import ExecutionService
from core.domain.enums.execution_status import ExecutionStatus
from core.domain.value_objects.execution_id import ExecutionID
from konozy_sdk.logging import get_logger
from konozy_sdk.utils.datetime import utc_now

from .bus import EventBusProtocol
from .events import Event, EventMetadata
from .models import ExecutionContext, StepResult, WorkflowResult
from .workflow import WorkflowDefinition, WorkflowStep


class Orchestrator:
    """Orchestrator for running workflows with eventing and execution tracking."""

    def __init__(
        self,
        execution_service: ExecutionService,
        event_bus: EventBusProtocol,
        service: str,
        operation: str | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            execution_service: ExecutionService for recording executions
            event_bus: EventBusProtocol for publishing events
            service: Service name
            operation: Optional operation name
        """
        self._execution_service = execution_service
        self._event_bus = event_bus
        self._service = service
        self._operation = operation
        self._logger = get_logger("orchestration.orchestrator")

    async def run(
        self, workflow: WorkflowDefinition, initial_input: object | None = None
    ) -> WorkflowResult:
        """Run a workflow.

        Args:
            workflow: WorkflowDefinition to run
            initial_input: Optional initial input for the first step

        Returns:
            WorkflowResult with execution details
        """
        started_at = utc_now()

        # Generate execution ID
        execution_id = ExecutionID.generate(
            service=self._service, operation=self._operation or workflow.name
        )

        # Build execution context
        ctx = ExecutionContext(
            execution_id=execution_id,
            service=self._service,
            operation=self._operation or workflow.operation,
            started_at=started_at,
        )

        self._logger.info(
            "workflow_starting",
            execution_id=execution_id.value,
            workflow_name=workflow.name,
            service=self._service,
            operation=self._operation,
            step_count=len(workflow.steps),
        )

        # Publish workflow.started event
        await self._publish_event(
            name="workflow.started",
            execution_id=execution_id,
            payload={"workflow_name": workflow.name, "step_count": len(workflow.steps)},
        )

        step_results: list[StepResult] = []
        last_result = initial_input
        workflow_succeeded = True

        # Execute steps in sequence
        for step in workflow.steps:
            step_result = await self._execute_step(ctx, step, last_result)
            step_results.append(step_result)

            if not step_result.success:
                # Step failed - stop workflow
                workflow_succeeded = False
                self._logger.warning(
                    "workflow_step_failed",
                    execution_id=execution_id.value,
                    step_name=step.name,
                    error=step_result.error,
                )
                break

            last_result = step_result.output

        finished_at = utc_now()

        # Determine final status
        final_status = ExecutionStatus.SUCCESS if workflow_succeeded else ExecutionStatus.FAILED

        # Record execution
        command = RecordExecutionCommand(
            execution_id=execution_id,
            service=self._service,
            operation=self._operation or workflow.operation,
            status=final_status.value,
            started_at=started_at,
            finished_at=finished_at,
        )
        await self._execution_service.record_execution(command)

        # Build workflow result
        result = WorkflowResult(
            execution_id=execution_id,
            service=self._service,
            operation=self._operation or workflow.operation,
            status=final_status,
            started_at=started_at,
            finished_at=finished_at,
            steps=step_results,
        )

        # Publish workflow.finished event
        await self._publish_event(
            name="workflow.finished",
            execution_id=execution_id,
            payload={
                "workflow_name": workflow.name,
                "status": final_status.value,
                "step_count": len(step_results),
                "success_count": sum(1 for s in step_results if s.success),
            },
        )

        self._logger.info(
            "workflow_finished",
            execution_id=execution_id.value,
            workflow_name=workflow.name,
            status=final_status.value,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
        )

        return result

    async def _execute_step(
        self, ctx: ExecutionContext, step: WorkflowStep, input_: object | None
    ) -> StepResult:
        """Execute a single workflow step with retry logic.

        Args:
            ctx: ExecutionContext
            step: WorkflowStep to execute
            input_: Input from previous step (or initial input)

        Returns:
            StepResult with execution details
        """
        step_started_at = utc_now()
        step_name = step.name
        policy = step.retry_policy

        # Publish step.started event
        await self._publish_event(
            name="workflow.step.started",
            execution_id=ctx.execution_id,
            payload={"step_name": step_name},
        )

        attempts = 0
        last_error: Exception | None = None

        # Retry loop
        for attempt in range(1, policy.max_attempts + 1):
            attempts = attempt
            try:
                # Execute activity
                output = await step.activity(ctx, input_)

                # Success - calculate duration
                step_finished_at = utc_now()
                duration_ms = int((step_finished_at - step_started_at).total_seconds() * 1000)

                step_result = StepResult(
                    name=step_name,
                    success=True,
                    attempts=attempts,
                    duration_ms=duration_ms,
                    output=output,
                )

                # Publish step.succeeded event
                await self._publish_event(
                    name="workflow.step.succeeded",
                    execution_id=ctx.execution_id,
                    payload={"step_name": step_name, "attempts": attempts},
                )

                return step_result

            except Exception as exc:
                last_error = exc
                self._logger.warning(
                    "step_attempt_failed",
                    execution_id=ctx.execution_id.value,
                    step_name=step_name,
                    attempt=attempt,
                    max_attempts=policy.max_attempts,
                    error=str(exc),
                )

                # If we have more attempts, wait before retry
                if attempt < policy.max_attempts:
                    if policy.backoff_seconds > 0:
                        await asyncio.sleep(policy.backoff_seconds)

        # All attempts failed
        step_finished_at = utc_now()
        duration_ms = int((step_finished_at - step_started_at).total_seconds() * 1000)

        error_str = str(last_error) if last_error else "Unknown error"

        step_result = StepResult(
            name=step_name,
            success=False,
            attempts=attempts,
            duration_ms=duration_ms,
            error=error_str,
        )

        # Publish step.failed event
        await self._publish_event(
            name="workflow.step.failed",
            execution_id=ctx.execution_id,
            payload={
                "step_name": step_name,
                "attempts": attempts,
                "error": error_str,
            },
        )

        return step_result

    async def _publish_event(
        self, name: str, execution_id: ExecutionID, payload: dict[str, object]
    ) -> None:
        """Publish an event.

        Args:
            name: Event name
            execution_id: ExecutionID
            payload: Event payload
        """
        metadata = EventMetadata(
            execution_id=execution_id.value,
            service=self._service,
            operation=self._operation,
            timestamp=utc_now(),
        )
        event = Event(name=name, payload=payload, metadata=metadata)
        await self._event_bus.publish(event)
