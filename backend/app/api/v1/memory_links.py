"""Memory integration API: link memories to tasks/workflows, and read them across employees.

Makes an existing memory a shared platform resource. Three association surfaces
over the *same* Memory Engine records — nothing here stores memory content:

    GET    /memories                                   the user's memories (+ search)
    GET    /tasks/{task_id}/memories                   memories a task references
    POST   /tasks/{task_id}/memories                   reference a memory from a task
    DELETE /tasks/{task_id}/memories/{memory_id}       drop that reference
    GET    /workflows/{workflow_id}/memories           memories a workflow references
    POST   /workflows/{workflow_id}/memories           reference a memory from a workflow
    DELETE /workflows/{workflow_id}/memories/{memory_id} drop that reference

Ownership and auth are the reused chains': the task/workflow through their own
services, the memory through its Employee → User chain. Routers only translate
HTTP; the service decides. Existing endpoints (``/employees/{id}/memories`` and
friends) are unchanged, so nothing here is a breaking change.
"""

import uuid
from typing import List, Optional, Sequence, Tuple

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUserDep, MemoryLinkServiceDep
from app.models.memory import Memory
from app.schemas.memory_link import (
    MemoryLinkCreate,
    UserMemoryListResponse,
    UserMemoryResponse,
)
from app.services.memory_link_service import (
    MemoryLinkNotFoundError,
    MemoryReferenceError,
)
from app.services.task_service import TaskAccessDeniedError, TaskNotFoundError
from app.services.workflow_service import (
    WorkflowAccessDeniedError,
    WorkflowNotFoundError,
)
from app.utils.constants import MemoryType

router = APIRouter(tags=["Memory Integration"])

_TASK_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {"description": "The task belongs to another user."},
    status.HTTP_404_NOT_FOUND: {
        "description": "The task, or the referenced memory, does not exist."
    },
}

_WORKFLOW_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The workflow belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The workflow, or the referenced memory, does not exist."
    },
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a domain error into its HTTP equivalent, in one place.

    Ownership misses read as 404/403 exactly as their own domains define them;
    a bad memory reference and a missing link both read as 404, since from the
    caller's side each names something that isn't there for them.
    """
    if isinstance(exc, (TaskNotFoundError, WorkflowNotFoundError)):
        label = "Task" if isinstance(exc, TaskNotFoundError) else "Workflow"
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found."
        )
    if isinstance(exc, TaskAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this task.",
        )
    if isinstance(exc, WorkflowAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workflow.",
        )
    if isinstance(exc, MemoryReferenceError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found."
        )
    if isinstance(exc, MemoryLinkNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="That memory isn't linked here.",
        )
    raise exc


def _to_memory(row: Tuple[Memory, str]) -> UserMemoryResponse:
    """Build the public shape from a ``(Memory, employee_name)`` row."""
    memory, employee_name = row
    return UserMemoryResponse(
        id=memory.id,
        employee_id=memory.employee_id,
        employee_name=employee_name,
        memory_type=memory.memory_type,
        content=memory.content,
        importance_score=memory.importance_score,
        created_at=memory.created_at,
    )


def _to_memories(rows: Sequence[Tuple[Memory, str]]) -> List[UserMemoryResponse]:
    return [_to_memory(row) for row in rows]


# --- User-wide read / search (the shared-resource access) ----------------


@router.get(
    "/memories",
    response_model=UserMemoryListResponse,
    tags=["Memory Integration"],
    summary="List (and search) the authenticated user's memories across employees",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing or invalid credentials."
        }
    },
)
def list_user_memories(
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
    q: Optional[str] = Query(
        default=None,
        max_length=200,
        description="Case-insensitive substring to match in memory content.",
    ),
    memory_type: Optional[MemoryType] = Query(
        default=None,
        description="Filter by memory type (permanent, working, learned).",
    ),
    min_importance: Optional[float] = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Only return memories with importance_score >= this value.",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of memories to return (1-100, default 50).",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of memories to skip for pagination (default 0).",
    ),
) -> UserMemoryListResponse:
    """Return the authenticated user's memories, newest first, with the total.

    A shared-resource read: memories from *every* one of the user's employees,
    addressable without naming an employee first. ``q`` searches memory content;
    ``memory_type`` and ``min_importance`` reuse the Memory Engine's filters.
    Returns an empty page when nothing matches.
    """
    rows, total = service.search_memories(
        current_user,
        keyword=q,
        memory_type=memory_type,
        min_importance=min_importance,
        limit=limit,
        offset=offset,
    )
    return UserMemoryListResponse(items=_to_memories(rows), total=total)


# --- Task ↔ memory -------------------------------------------------------


@router.get(
    "/tasks/{task_id}/memories",
    response_model=List[UserMemoryResponse],
    summary="List the memories a task references",
    responses=_TASK_RESPONSES,
)
def list_task_memories(
    task_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> List[UserMemoryResponse]:
    """Return the memories referenced by the task, in the order they were linked."""
    try:
        rows = service.list_task_memories(current_user, task_id)
    except (TaskNotFoundError, TaskAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_memories(rows)


@router.post(
    "/tasks/{task_id}/memories",
    response_model=UserMemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reference an existing memory from a task",
    responses=_TASK_RESPONSES,
)
def link_task_memory(
    task_id: uuid.UUID,
    data: MemoryLinkCreate,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> UserMemoryResponse:
    """Link an existing memory to the task.

    Both must belong to the authenticated user. Linking an already-linked memory
    returns it unchanged (``201``) rather than erroring — the reference is
    idempotent. The memory content is never copied; only the reference is stored.
    """
    try:
        row = service.attach_memory_to_task(current_user, task_id, data.memory_id)
    except (
        TaskNotFoundError,
        TaskAccessDeniedError,
        MemoryReferenceError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_memory(row)


@router.delete(
    "/tasks/{task_id}/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a task's reference to a memory",
    responses=_TASK_RESPONSES,
)
def unlink_task_memory(
    task_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> None:
    """Drop the task's reference to the memory. The memory itself is untouched."""
    try:
        service.detach_memory_from_task(current_user, task_id, memory_id)
    except (
        TaskNotFoundError,
        TaskAccessDeniedError,
        MemoryLinkNotFoundError,
    ) as exc:
        raise _to_http_exception(exc)


# --- Workflow ↔ memory ---------------------------------------------------


@router.get(
    "/workflows/{workflow_id}/memories",
    response_model=List[UserMemoryResponse],
    summary="List the memories a workflow references",
    responses=_WORKFLOW_RESPONSES,
)
def list_workflow_memories(
    workflow_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> List[UserMemoryResponse]:
    """Return the memories referenced by the workflow, in link order."""
    try:
        rows = service.list_workflow_memories(current_user, workflow_id)
    except (WorkflowNotFoundError, WorkflowAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_memories(rows)


@router.post(
    "/workflows/{workflow_id}/memories",
    response_model=UserMemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reference an existing memory from a workflow",
    responses=_WORKFLOW_RESPONSES,
)
def link_workflow_memory(
    workflow_id: uuid.UUID,
    data: MemoryLinkCreate,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> UserMemoryResponse:
    """Link an existing memory to the workflow as reference material.

    Both must belong to the authenticated user. Idempotent, and content is never
    copied — the workflow references the same record the Memory Engine owns.
    """
    try:
        row = service.attach_memory_to_workflow(
            current_user, workflow_id, data.memory_id
        )
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        MemoryReferenceError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_memory(row)


@router.delete(
    "/workflows/{workflow_id}/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a workflow's reference to a memory",
    responses=_WORKFLOW_RESPONSES,
)
def unlink_workflow_memory(
    workflow_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryLinkServiceDep,
) -> None:
    """Drop the workflow's reference to the memory. The memory itself is untouched."""
    try:
        service.detach_memory_from_workflow(current_user, workflow_id, memory_id)
    except (
        WorkflowNotFoundError,
        WorkflowAccessDeniedError,
        MemoryLinkNotFoundError,
    ) as exc:
        raise _to_http_exception(exc)
