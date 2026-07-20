"""Workflow execution history endpoints (Sprint 18.10).

A run now outlives the request that started it, so it needs somewhere to be
looked up. These are that: one recorded run in full, and a way to run it again.

Deliberately a separate router at ``/workflow-executions`` rather than more
paths under ``/workflows``. An execution is addressed by its own id and needs no
workflow in the path to find it, and the sprint is explicit that the existing
workflow API is not to be redesigned. Listing a *workflow's* runs stays where it
belongs — under that workflow — because that one really is a question about a
workflow.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.v1.workflows import execution_response
from app.core.dependencies import (
    CurrentUserDep,
    WorkflowExecutionHistoryServiceDep,
    WorkflowExecutionServiceDep,
)
from app.models.workflow_execution import WorkflowExecution
from app.schemas.workflow import (
    WorkflowExecutionDetailResponse,
    WorkflowExecutionLogResponse,
    WorkflowExecutionResponse,
    WorkflowExecutionStepRecordResponse,
)
from app.services.workflow_execution_history_service import (
    TRIGGER_RETRY,
    ExecutionAccessDeniedError,
    ExecutionNotFoundError,
)
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)

router = APIRouter(prefix="/workflow-executions", tags=["Workflow Executions"])

_EXECUTION_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "The run belongs to another user's workflow."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The run does not exist."},
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a domain error into its HTTP equivalent.

    The same mapping the workflow router makes, extended with the two errors
    history adds — so a missing run and a missing workflow answer alike.
    """
    if isinstance(exc, (ExecutionNotFoundError, WorkflowNotFoundError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found."
        )
    if isinstance(exc, (ExecutionAccessDeniedError, WorkflowAccessDeniedError)):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this execution.",
        )
    if isinstance(exc, InvalidStatusTransitionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, WorkflowValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    raise exc


def _to_detail(execution: WorkflowExecution) -> WorkflowExecutionDetailResponse:
    """Build the full public representation of one recorded run.

    Constructed field by field rather than by attribute validation because the
    two collections need mapping of their own, and doing it here keeps the
    stored rows from deciding the wire shape.
    """
    return WorkflowExecutionDetailResponse(
        id=execution.id,
        workflow_id=execution.workflow_id,
        status=execution.status,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_ms=execution.duration_ms,
        total_step_count=execution.total_step_count,
        completed_step_count=execution.completed_step_count,
        failed_step_id=execution.failed_step_id,
        error=execution.error,
        trigger=execution.trigger,
        retry_of_execution_id=execution.retry_of_execution_id,
        steps=[
            WorkflowExecutionStepRecordResponse.model_validate(step)
            for step in execution.steps
        ],
        logs=[
            WorkflowExecutionLogResponse.model_validate(log) for log in execution.logs
        ],
    )


@router.get(
    "/{execution_id}",
    response_model=WorkflowExecutionDetailResponse,
    summary="Get one recorded workflow run",
    responses=_EXECUTION_RESPONSES,
)
def get_execution(
    execution_id: uuid.UUID,
    current_user: CurrentUserDep,
    history: WorkflowExecutionHistoryServiceDep,
) -> WorkflowExecutionDetailResponse:
    """Return one past run: how it went, what each step did, and its log.

    An execution has no owner of its own — it belongs to a workflow, and that
    workflow has one — so access is decided by the workflow, exactly as every
    other read of it is.
    """
    try:
        execution = history.get_execution(current_user, execution_id)
    except (ExecutionNotFoundError, ExecutionAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_detail(execution)


@router.post(
    "/{execution_id}/retry",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a workflow again, repeating a past run",
    responses={
        **_EXECUTION_RESPONSES,
        status.HTTP_409_CONFLICT: {
            "description": "The workflow is no longer published, so cannot be run."
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The workflow's graph can no longer be run as authored."
        },
    },
)
def retry_execution(
    execution_id: uuid.UUID,
    current_user: CurrentUserDep,
    history: WorkflowExecutionHistoryServiceDep,
    service: WorkflowExecutionServiceDep,
) -> WorkflowExecutionResponse:
    """Run the workflow again, recording a *new* run that points at this one.

    The run being retried is never touched: history is immutable, and a retry
    that edited what it repeated would destroy the record it was started from.
    ``201`` because this creates something.

    The workflow is run **as it is now**, not as it was. Its graph may have been
    edited since, so a retry can legitimately behave differently — or be refused
    where the original succeeded, if it has since been unpublished or edited into
    something unrunnable. That is why the refusals below are possible at all.
    """
    try:
        original = history.get_for_retry(current_user, execution_id)
    except (ExecutionNotFoundError, ExecutionAccessDeniedError) as exc:
        raise _to_http_exception(exc)

    try:
        tracked = service.execute_and_record(
            current_user,
            original.workflow_id,
            trigger=TRIGGER_RETRY,
            retry_of_execution_id=original.id,
        )
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)

    # The same mapping the execute endpoint uses. A retry answers with a run, so
    # it answers in the shape a run has — two copies of that mapping would be the
    # thing worth avoiding, not the shared import.
    return execution_response(tracked.result, tracked.execution)
