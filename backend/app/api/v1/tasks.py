"""Task Engine API endpoints (Sprint 19).

Tasks are first-class executable work managed by the Workflow platform: a task
is described, assigned to an AI employee, shaped by a workflow, and — through
the execute endpoint — launched on the existing execution engine.

Execution answers in the workflow domain's own shapes
(:class:`WorkflowExecutionResponse` and friends), built by the same mapping the
workflow endpoints use. A task's run *is* a workflow run; a second DTO for it
would be a second execution vocabulary, which this sprint exists to avoid.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from app.api.v1.workflows import execution_response
from app.core.dependencies import CurrentUserDep, TaskServiceDep
from app.models.task import Task
from app.models.workflow_execution import WorkflowExecution
from app.schemas.task import (
    TaskCommandRequest,
    TaskCreate,
    TaskDuplicateRequest,
    TaskEmployeeRef,
    TaskExecuteRequest,
    TaskExecutionListResponse,
    TaskResponse,
    TaskUpdate,
    TaskWorkflowRef,
)
from app.schemas.workflow import (
    WorkflowExecutionResponse,
    WorkflowExecutionSummaryResponse,
)
from app.services.task_service import (
    InvalidTaskCommandError,
    TaskAccessDeniedError,
    TaskNotFoundError,
    TaskService,
    TaskValidationError,
)
from app.services.workflow_service import (
    InvalidStatusTransitionError,
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

_OWNERSHIP_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {"description": "The task belongs to another user."},
    status.HTTP_404_NOT_FOUND: {"description": "The task does not exist."},
}

_EXECUTE_RESPONSES = {
    **_OWNERSHIP_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": (
            "The task's status forbids a launch, or its workflow is a draft "
            "or archived, so cannot be run."
        )
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "description": (
            "The task has no workflow attached, or the workflow's graph "
            "cannot be translated into runnable steps."
        )
    },
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a domain error into its HTTP equivalent.

    One place so every endpoint maps the same error to the same status. The
    workflow domain's errors are included because the execute endpoints let
    them surface — a task run refuses exactly as a workflow run does.
    """
    if isinstance(exc, TaskNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found."
        )
    if isinstance(exc, TaskAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task.",
        )
    if isinstance(exc, (InvalidTaskCommandError, InvalidStatusTransitionError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (TaskValidationError, WorkflowValidationError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    if isinstance(exc, WorkflowNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found."
        )
    if isinstance(exc, WorkflowAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workflow.",
        )
    raise exc


def _to_response(
    task: Task,
    latest: Optional[WorkflowExecution],
    execution_count: int,
) -> TaskResponse:
    """Build the full public representation of one task.

    Constructed field by field rather than by attribute validation because the
    two references and the execution overview need mapping of their own, and
    doing it here keeps the stored rows from deciding the wire shape.
    """
    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        business_id=task.business_id,
        name=task.name,
        description=task.description,
        status=task.status,
        priority=task.priority,
        execution_mode=task.execution_mode,
        progress=task.progress,
        workflow=(
            TaskWorkflowRef(
                id=task.workflow.id,
                name=task.workflow.name,
                status=task.workflow.status,
            )
            if task.workflow is not None
            else None
        ),
        assignee=(
            TaskEmployeeRef(id=task.assignee.id, name=task.assignee.name)
            if task.assignee is not None
            else None
        ),
        latest_execution=(
            WorkflowExecutionSummaryResponse.model_validate(latest)
            if latest is not None
            else None
        ),
        execution_count=execution_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _respond(service: TaskService, task: Task) -> TaskResponse:
    """One task, with its execution overview looked up alongside it."""
    latest, count = service.execution_overview(task)
    return _to_response(task, latest, count)


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="List the authenticated user's tasks",
)
def list_tasks(
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> List[TaskResponse]:
    """Return every task owned by the authenticated user.

    Each task carries its resolved workflow and assignee references and its
    latest run, so the directory renders without follow-up requests.
    """
    return [_respond(service, task) for task in service.list_tasks(current_user)]


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task for the authenticated user",
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The name is empty, or a referenced workflow or employee isn't yours."
        }
    },
)
def create_task(
    data: TaskCreate,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> TaskResponse:
    """Create a task owned by the authenticated user.

    The owner is taken from the bearer token, never from the payload. A created
    task opens ``pending`` — describing work never starts it.
    """
    try:
        task = service.create_task(current_user, data)
    except TaskValidationError as exc:
        raise _to_http_exception(exc)
    return _respond(service, task)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get one of the authenticated user's tasks",
    responses=_OWNERSHIP_RESPONSES,
)
def get_task(
    task_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> TaskResponse:
    """Return a single task, with references and latest run resolved."""
    try:
        task = service.get_task(current_user, task_id)
    except (TaskNotFoundError, TaskAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _respond(service, task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update one of the authenticated user's tasks",
    responses=_OWNERSHIP_RESPONSES,
)
def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> TaskResponse:
    """Partially update a task. Only supplied fields change.

    Sending ``workflow_id`` or ``employee_id`` assigns or reassigns; sending
    either as ``null`` clears it. Status changes go through the command
    endpoint instead — a status is earned, not written.
    """
    try:
        task = service.update_task(current_user, task_id, data)
    except (TaskNotFoundError, TaskAccessDeniedError, TaskValidationError) as exc:
        raise _to_http_exception(exc)
    return _respond(service, task)


@router.post(
    "/{task_id}/duplicate",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a task",
    responses=_OWNERSHIP_RESPONSES,
)
def duplicate_task(
    task_id: uuid.UUID,
    data: TaskDuplicateRequest,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> TaskResponse:
    """Copy a task's description into a new pending task.

    The copy inherits the plan — never the run. Omitting ``name`` derives one
    from the source (``… (copy)``).
    """
    try:
        clone = service.duplicate_task(current_user, task_id, data.name)
    except (TaskNotFoundError, TaskAccessDeniedError, TaskValidationError) as exc:
        raise _to_http_exception(exc)
    return _respond(service, clone)


@router.post(
    "/{task_id}/command",
    response_model=TaskResponse,
    summary="Apply a state command to a task",
    responses={
        **_OWNERSHIP_RESPONSES,
        status.HTTP_409_CONFLICT: {
            "description": "The task's current status does not accept this command."
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The command is not one the platform knows."
        },
    },
)
def run_command(
    task_id: uuid.UUID,
    data: TaskCommandRequest,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> TaskResponse:
    """Queue, pause, resume, cancel, or retry a task.

    Legality is decided by the task's current status against the platform's one
    command table — the same table the UI disables buttons from.
    """
    try:
        task = service.run_command(current_user, task_id, data.command)
    except (
        TaskNotFoundError,
        TaskAccessDeniedError,
        TaskValidationError,
        InvalidTaskCommandError,
    ) as exc:
        raise _to_http_exception(exc)
    return _respond(service, task)


@router.post(
    "/{task_id}/execute",
    response_model=WorkflowExecutionResponse,
    summary="Launch the task's workflow on the execution engine",
    responses=_EXECUTE_RESPONSES,
)
def execute_task(
    task_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
    data: TaskExecuteRequest | None = None,
) -> WorkflowExecutionResponse:
    """Run the task's attached workflow through the existing execution service.

    The run is recorded in workflow execution history, linked to this task, and
    the task's status and progress reflect how it went. A workflow that runs
    but whose step fails returns 200 with ``status="FAILED"`` — the call
    succeeded, the run did not — exactly as the workflow's own execute
    endpoint answers.
    """
    try:
        _, tracked = service.execute_task(
            current_user,
            task_id,
            initial_inputs=data.inputs if data else None,
        )
    except (
        TaskNotFoundError,
        TaskAccessDeniedError,
        TaskValidationError,
        InvalidTaskCommandError,
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return execution_response(tracked.result, tracked.execution)


@router.post(
    "/{task_id}/executions/{execution_id}/retry",
    response_model=WorkflowExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the task's workflow again, repeating one of its past runs",
    responses=_EXECUTE_RESPONSES,
)
def retry_task_execution(
    task_id: uuid.UUID,
    execution_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
) -> WorkflowExecutionResponse:
    """Repeat one of this task's recorded runs as a new run.

    The original is never touched — history is immutable, and the new run
    points back at the one it repeats. The new run is linked to this task and
    the task reflects its outcome. ``201`` because this creates something.
    """
    try:
        _, tracked = service.retry_execution(current_user, task_id, execution_id)
    except (
        TaskNotFoundError,
        TaskAccessDeniedError,
        TaskValidationError,
        InvalidTaskCommandError,
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        InvalidStatusTransitionError,
        WorkflowValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return execution_response(tracked.result, tracked.execution)


@router.get(
    "/{task_id}/executions",
    response_model=TaskExecutionListResponse,
    summary="List the runs this task launched",
    responses=_OWNERSHIP_RESPONSES,
)
def list_task_executions(
    task_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: TaskServiceDep,
    skip: int = 0,
    limit: int = 50,
) -> TaskExecutionListResponse:
    """Return this task's runs, newest first.

    Summaries only, in the workflow domain's own history shape. Fetch one run
    through ``/workflow-executions/{id}`` to see its steps and log — an
    execution is the same record whichever door it is reached through.
    """
    try:
        rows, total = service.list_executions(
            current_user, task_id, skip=skip, limit=limit
        )
    except (TaskNotFoundError, TaskAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return TaskExecutionListResponse(
        items=[WorkflowExecutionSummaryResponse.model_validate(row) for row in rows],
        total=total,
    )
