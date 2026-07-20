"""Workflow API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import (
    CurrentUserDep,
    WorkflowExecutionHistoryServiceDep,
    WorkflowExecutionServiceDep,
    WorkflowServiceDep,
)
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowDuplicateRequest,
    WorkflowExecuteRequest,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowExecutionStepResponse,
    WorkflowExecutionSummaryResponse,
    WorkflowResponse,
    WorkflowRestoreRequest,
    WorkflowSummaryResponse,
    WorkflowUpdate,
)
from app.services.runtime.workflow_models import WorkflowExecutionResult
from app.services.workflow_graph import node_count
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])

_OWNERSHIP_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "The workflow belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The workflow does not exist."},
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a domain error into its HTTP equivalent.

    One place so every endpoint maps the same error to the same status, and the
    same way the employee domain does.
    """
    if isinstance(exc, WorkflowNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found."
        )
    if isinstance(exc, WorkflowAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workflow.",
        )
    if isinstance(exc, InvalidStatusTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, WorkflowValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    raise exc


def _to_response(workflow: Workflow) -> WorkflowResponse:
    """Build the full public representation, including the derived node count.

    Constructed field by field rather than via ``model_validate``: ``node_count``
    is derived from the stored graph rather than stored alongside it, so
    attribute-based validation would have nothing to read.
    """
    return WorkflowResponse(
        id=workflow.id,
        user_id=workflow.user_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        node_count=node_count(workflow.graph),
        archived_at=workflow.archived_at,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        graph=workflow.graph,
    )


def execution_response(
    result: WorkflowExecutionResult, execution: WorkflowExecution
) -> WorkflowExecutionResponse:
    """Map the runtime's result into the API's own execution DTO.

    The runtime model and its nested references stay behind the service
    boundary; only these flat, documented fields cross the wire.

    Since Sprint 18.10 the run also has a record, which supplies the identity
    and the timings the runtime does not carry.
    """
    return WorkflowExecutionResponse(
        workflow_id=result.workflow_id,
        execution_id=execution.id,
        status=result.workflow_status,
        completed_step_count=result.completed_step_count,
        total_step_count=result.total_step_count,
        failed_step_id=result.failed_step_id,
        steps=[
            WorkflowExecutionStepResponse(
                step_id=step.step_id,
                capability=step.capability_name,
                status=step.execution_status,
                outputs=dict(step.outputs),
            )
            for step in result.step_references
        ],
        final_outputs=dict(result.final_outputs),
        # `result_metadata["error"]` is the coordinator's failure reason on a
        # FAILED run; absent on success.
        error=result.result_metadata.get("error"),
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_ms=execution.duration_ms,
    )


def _to_summary(workflow: Workflow) -> WorkflowSummaryResponse:
    """The list representation — everything but the graph."""
    return WorkflowSummaryResponse(
        id=workflow.id,
        user_id=workflow.user_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        node_count=node_count(workflow.graph),
        archived_at=workflow.archived_at,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


@router.get(
    "",
    response_model=List[WorkflowSummaryResponse],
    summary="List the authenticated user's workflows",
)
def list_workflows(
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> List[WorkflowSummaryResponse]:
    """Return every workflow owned by the authenticated user.

    Graphs are omitted; fetch one workflow to get its structure.
    """
    return [_to_summary(w) for w in service.list_workflows(current_user)]


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow for the authenticated user",
)
def create_workflow(
    data: WorkflowCreate,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Create a workflow owned by the authenticated user.

    The owner is taken from the bearer token, never from the payload. Omitting
    ``graph`` creates a blank canvas.
    """
    try:
        workflow = service.create_workflow(current_user, data)
    except WorkflowValidationError as exc:
        raise _to_http_exception(exc)
    return _to_response(workflow)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Get one of the authenticated user's workflows",
    responses=_OWNERSHIP_RESPONSES,
)
def get_workflow(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Return a single workflow, including its graph."""
    try:
        workflow = service.get_workflow(current_user, workflow_id)
    except (WorkflowNotFoundError, WorkflowAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_response(workflow)


@router.patch(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Update one of the authenticated user's workflows",
    responses=_OWNERSHIP_RESPONSES,
)
def update_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowUpdate,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Partially update a workflow. Only supplied fields change.

    Sending ``status`` publishes or unpublishes it. Archiving goes through the
    archive endpoint instead.
    """
    try:
        workflow = service.update_workflow(current_user, workflow_id, data)
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(workflow)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's workflows",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_workflow(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> Response:
    """Delete a workflow permanently.

    Unlike an employee this is a hard delete: a workflow owns no memories,
    sessions or history that would need to outlive it.
    """
    try:
        service.delete_workflow(current_user, workflow_id)
    except (WorkflowNotFoundError, WorkflowAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workflow_id}/archive",
    response_model=WorkflowResponse,
    summary="Archive a workflow",
    responses=_OWNERSHIP_RESPONSES,
)
def archive_workflow(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Retire a workflow without destroying it."""
    try:
        workflow = service.archive_workflow(current_user, workflow_id)
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(workflow)


@router.post(
    "/{workflow_id}/restore",
    response_model=WorkflowResponse,
    summary="Restore an archived workflow",
    responses=_OWNERSHIP_RESPONSES,
)
def restore_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowRestoreRequest,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Bring an archived workflow back to ``draft``."""
    try:
        workflow = service.restore_workflow(current_user, workflow_id, data.status)
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(workflow)


@router.post(
    "/{workflow_id}/duplicate",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a workflow",
    responses=_OWNERSHIP_RESPONSES,
)
def duplicate_workflow(
    workflow_id: uuid.UUID,
    data: WorkflowDuplicateRequest,
    current_user: CurrentUserDep,
    service: WorkflowServiceDep,
) -> WorkflowResponse:
    """Copy a workflow's structure into a new draft.

    Omitting ``name`` derives one from the source (``… (copy)``).
    """
    try:
        clone = service.duplicate_workflow(current_user, workflow_id, data.name)
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(clone)


@router.post(
    "/{workflow_id}/execute",
    response_model=WorkflowExecutionResponse,
    summary="Run a published workflow through the execution engine",
    responses={
        **_OWNERSHIP_RESPONSES,
        status.HTTP_409_CONFLICT: {
            "description": "The workflow is a draft or archived, so cannot be run."
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The workflow's graph cannot be translated into runnable steps."
        },
    },
)
def execute_workflow(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: WorkflowExecutionServiceDep,
    data: WorkflowExecuteRequest | None = None,
) -> WorkflowExecutionResponse:
    """Translate a published workflow's graph and run it on the Sprint 15.15 engine.

    Rejects (4xx) when the workflow is missing, another user's, not published,
    or can't be translated. A workflow that runs but whose step fails returns
    200 with ``status="FAILED"`` — the call succeeded, the run did not.

    Authoring and execution stay separate: this endpoint is the only bridge, and
    it never mutates the workflow or touches the runtime's semantics.
    """
    try:
        tracked = service.execute_and_record(
            current_user,
            workflow_id,
            initial_inputs=data.inputs if data else None,
        )
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return execution_response(tracked.result, tracked.execution)


@router.get(
    "/{workflow_id}/executions",
    response_model=WorkflowExecutionListResponse,
    summary="List a workflow's past runs",
    responses=_OWNERSHIP_RESPONSES,
)
def list_workflow_executions(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    history: WorkflowExecutionHistoryServiceDep,
    skip: int = 0,
    limit: int = 50,
) -> WorkflowExecutionListResponse:
    """Return this workflow's runs, newest first (Sprint 18.10).

    Summaries only — how each run went, when, and for how long. Fetch one run to
    see its steps and log.
    """
    try:
        rows, total = history.list_for_workflow(
            current_user, workflow_id, skip=skip, limit=limit
        )
    except (WorkflowNotFoundError, WorkflowAccessDeniedError) as exc:
        raise _to_http_exception(exc)

    return WorkflowExecutionListResponse(
        items=[WorkflowExecutionSummaryResponse.model_validate(row) for row in rows],
        total=total,
    )
