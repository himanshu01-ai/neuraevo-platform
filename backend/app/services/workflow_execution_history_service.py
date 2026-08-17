"""Workflow execution history (Sprint 18.10 — a run you can look back at).

Owns the business rules around *remembering* a run: recording one when it ends,
reading them back, and starting a fresh one that repeats an earlier one. It does
not run anything itself — :class:`WorkflowExecutionService` still does that, and
the runtime still decides what a run means.

Ownership is not re-implemented. Every read and every retry goes through
:class:`WorkflowService` for "does this workflow exist and is it yours", so
there is one definition of that and history inherits it: an execution belongs to
the workflow it ran, and the workflow belongs to its owner.

Two rules shape everything here:

* **History is immutable.** Nothing updates an execution. A retry writes a new
  row that points back at the one it repeats, so the original stays exactly as
  it happened, and "what did it do last time" keeps its answer.
* **Nothing is recorded that the runtime did not produce or the service did not
  observe.** Timings come from the recorder wrapped around the router, the rest
  comes from the result. No detail is invented to fill a column.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from app.models.user import User
from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionLog,
    WorkflowExecutionStep,
)
from app.repositories.workflow_execution_repository import WorkflowExecutionRepository
from app.services.runtime.workflow_models import WorkflowExecutionResult
from app.services.workflow_execution_recorder import (
    ExecutionLog,
    TimingCapabilityRouter,
)
from app.services.workflow_service import (
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowService,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

#: How a run was started.
TRIGGER_MANUAL = "manual"
TRIGGER_RETRY = "retry"

#: The runtime's terminal statuses, as history stores them.
STATUS_COMPLETED = "COMPLETED"


class ExecutionNotFoundError(Exception):
    """Raised when an execution id matches nothing."""


class ExecutionAccessDeniedError(Exception):
    """Raised when an execution belongs to another user's workflow."""


class WorkflowExecutionHistoryService:
    """Records, reads and repeats workflow runs.

    Constructed with the request-scoped session (constructor injection; it
    instantiates no coordinator and runs nothing). Reuses
    :class:`WorkflowService` for ownership.
    """

    def __init__(self, session) -> None:
        self.session = session
        self.executions = WorkflowExecutionRepository(session)
        self.workflows = WorkflowService(session)

    # --- Recording -------------------------------------------------------

    def record(
        self,
        *,
        owner: User,
        workflow_id: uuid.UUID,
        result: WorkflowExecutionResult,
        started_at: datetime,
        finished_at: datetime,
        recorder: Optional[TimingCapabilityRouter] = None,
        log: Optional[ExecutionLog] = None,
        trigger: str = TRIGGER_MANUAL,
        retry_of_execution_id: Optional[uuid.UUID] = None,
    ) -> WorkflowExecution:
        """Write one finished run to history and return it.

        Called after the run is over, with what the run produced. The whole row —
        execution, steps and logs — is built in memory and added at once, so a
        run is either remembered completely or not at all.

        Deliberately forgiving of a partial result: a run that failed before its
        first step still gets a row, because "it started and got nowhere" is
        exactly the kind of thing history is for.
        """
        duration_ms = _elapsed_ms(started_at, finished_at)

        execution = WorkflowExecution(
            workflow_id=workflow_id,
            user_id=owner.id,
            status=result.workflow_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            total_step_count=result.total_step_count,
            completed_step_count=result.completed_step_count,
            failed_step_id=result.failed_step_id,
            error=result.result_metadata.get("error"),
            trigger=trigger,
            retry_of_execution_id=retry_of_execution_id,
        )

        artifacts_by_id = {a.reference_id: a for a in result.artifacts}

        for position, reference in enumerate(result.step_references):
            timing = recorder.timing_for(reference.step_id) if recorder else None
            execution.steps.append(
                WorkflowExecutionStep(
                    step_id=reference.step_id,
                    capability=reference.capability_name,
                    status=reference.execution_status,
                    position=position,
                    started_at=timing.started_at if timing else None,
                    finished_at=timing.finished_at if timing else None,
                    duration_ms=timing.duration_ms if timing else None,
                    outputs=dict(reference.outputs),
                    # Kept because it exists and was being thrown away: the API's
                    # execution response has never carried per-step metadata.
                    step_metadata=dict(reference.execution_metadata),
                    artifacts=[
                        _artifact_descriptor(artifacts_by_id[reference_id])
                        for reference_id in reference.artifact_reference_ids
                        if reference_id in artifacts_by_id
                    ],
                )
            )

        for sequence, record in enumerate(log.records if log else []):
            execution.logs.append(
                WorkflowExecutionLog(
                    sequence=sequence,
                    level=record.level,
                    message=record.message,
                    step_id=record.step_id,
                )
            )

        self.executions.add(execution)
        self.session.commit()
        logger.info(
            "Recorded execution %s of workflow %s: %s in %dms",
            execution.id,
            workflow_id,
            execution.status,
            duration_ms,
        )
        return execution

    # --- Reading ---------------------------------------------------------

    def list_for_workflow(
        self,
        owner: User,
        workflow_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[Sequence[WorkflowExecution], int]:
        """A workflow's runs, newest first, with the total count.

        Ownership is checked by loading the workflow through
        :class:`WorkflowService`, which raises not-found or access-denied exactly
        as every other workflow read does.
        """
        self.workflows.get_workflow(owner, workflow_id)  # ownership, reused
        rows = self.executions.list_by_workflow(workflow_id, skip=skip, limit=limit)
        return rows, self.executions.count_by_workflow(workflow_id)

    def get_execution(
        self, owner: User, execution_id: uuid.UUID
    ) -> WorkflowExecution:
        """One run in full, with its steps and logs.

        An execution has no owner of its own: it belongs to a workflow, and that
        workflow has one. So the check is made against the workflow, which keeps
        one definition of ownership rather than adding a second.
        """
        execution = self.executions.get_with_detail(execution_id)
        if execution is None:
            raise ExecutionNotFoundError(str(execution_id))

        try:
            self.workflows.get_workflow(owner, execution.workflow_id)
        except WorkflowNotFoundError as exc:
            # The workflow is gone but its history is not — treat the run as gone
            # too rather than serving a record no one can place.
            raise ExecutionNotFoundError(str(execution_id)) from exc
        except WorkflowAccessDeniedError as exc:
            raise ExecutionAccessDeniedError(str(execution_id)) from exc

        return execution

    def get_for_retry(
        self, owner: User, execution_id: uuid.UUID
    ) -> WorkflowExecution:
        """The run a retry is about to repeat, once it is known to be the caller's.

        Returns the original without steps or logs — a retry needs its workflow
        and its id, not what it did.
        """
        execution = self.executions.get_by_id(execution_id)
        if execution is None:
            raise ExecutionNotFoundError(str(execution_id))

        try:
            self.workflows.get_workflow(owner, execution.workflow_id)
        except WorkflowNotFoundError as exc:
            raise ExecutionNotFoundError(str(execution_id)) from exc
        except WorkflowAccessDeniedError as exc:
            raise ExecutionAccessDeniedError(str(execution_id)) from exc

        return execution


def _elapsed_ms(started_at: datetime, finished_at: datetime) -> int:
    """Milliseconds between two instants, never negative.

    A clock that steps backwards mid-run would otherwise store a negative
    duration, which no reader expects and no display handles.
    """
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _artifact_descriptor(artifact) -> dict:
    """A produced artifact as plain, storable description.

    Descriptors only. The artifact's *contents* stay wherever the capability put
    them; copying them into history would duplicate data the sprint is explicit
    about not duplicating, and would grow this table without bound.
    """
    return {
        "reference_id": artifact.reference_id,
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "name": artifact.name,
        "source_step": artifact.source_step,
        "source_capability": artifact.source_capability,
    }


def utc_now() -> datetime:
    """The clock history is measured against, in one place."""
    return datetime.now(timezone.utc)
