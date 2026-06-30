"""Memory API endpoints (nested under an employee)."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUserDep, MemoryServiceDep
from app.schemas.memory import MemoryCreate, MemoryResponse, MemoryUpdate
from app.schemas.memory_stats import MemoryStatsResponse
from app.utils.constants import MemoryType
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)
from app.services.memory_service import (
    MemoryAccessDeniedError,
    MemoryError,
    MemoryNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/memories", tags=["Memories"]
)

_OWNERSHIP_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
}

# Documented responses for the list endpoint. 422 (invalid query params) is
# added automatically by FastAPI.
_LIST_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
}

# Documented responses for the single-memory endpoints. 422 (invalid UUID) is
# added automatically by FastAPI from the path parameters.
_MEMORY_ITEM_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee or memory belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee or memory does not exist."
    },
}

# Maps domain exceptions to the (status code, detail) used in HTTP responses.
_DOMAIN_HTTP_MAP: list[tuple[type[Exception], int, str]] = [
    (EmployeeNotFoundError, status.HTTP_404_NOT_FOUND, "Employee not found."),
    (
        EmployeeAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this employee.",
    ),
    (MemoryNotFoundError, status.HTTP_404_NOT_FOUND, "Memory not found."),
    (
        MemoryAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "This memory does not belong to the specified employee.",
    ),
]


def _to_http_exception(exc: EmployeeError | MemoryError) -> HTTPException:
    """Translate an ownership/lookup domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a memory to one of the authenticated user's employees",
    responses=_OWNERSHIP_RESPONSES,
)
def create_memory(
    employee_id: uuid.UUID,
    data: MemoryCreate,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryResponse:
    """Create a memory for the given employee.

    The employee must belong to the authenticated user. Returns ``404`` if the
    employee does not exist and ``403`` if it belongs to another user. The
    ``memory_type`` is validated against the allowed set (``422`` otherwise).
    """
    try:
        memory = service.create_memory(current_user, employee_id, data)
    except EmployeeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )
    except EmployeeAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this employee.",
        )
    return MemoryResponse.model_validate(memory)


@router.get(
    "",
    response_model=List[MemoryResponse],
    summary="List memories for one of the authenticated user's employees",
    responses=_LIST_RESPONSES,
)
def list_memories(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
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
) -> List[MemoryResponse]:
    """List memories for the given employee, oldest first.

    The employee must belong to the authenticated user (``404``/``403``).
    Optional ``memory_type`` and ``min_importance`` filters narrow the result;
    ``limit``/``offset`` paginate it. Returns an empty list when nothing
    matches. Invalid query values yield ``422``.
    """
    try:
        memories = service.list_memories(
            current_user,
            employee_id,
            memory_type=memory_type,
            min_importance=min_importance,
            limit=limit,
            offset=offset,
        )
    except EmployeeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )
    except EmployeeAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this employee.",
        )
    return [MemoryResponse.model_validate(m) for m in memories]


@router.get(
    "/stats",
    response_model=MemoryStatsResponse,
    summary="Get aggregated memory statistics for one of the user's employees",
    responses=_LIST_RESPONSES,
)
def get_memory_stats(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryStatsResponse:
    """Return aggregated memory statistics for the given employee.

    Counts per memory type, the total, and the average importance score. The
    employee must belong to the authenticated user (``404``/``403``). An
    employee with no memories yields all-zero counts and a ``0.0`` average.
    """
    # Declared before ``/{memory_id}`` so the literal "stats" path is not
    # captured as a memory UUID.
    try:
        return service.get_memory_stats(current_user, employee_id)
    except (EmployeeError, MemoryError) as exc:
        raise _to_http_exception(exc)


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Get a single memory for one of the user's employees",
    responses=_MEMORY_ITEM_RESPONSES,
)
def get_memory(
    employee_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryResponse:
    """Return a single memory by id, scoped to the employee and user.

    Returns ``404`` if the employee or memory does not exist, and ``403`` if
    either belongs to another owner (or the memory belongs to a different
    employee). Invalid path UUIDs yield ``422``.
    """
    try:
        memory = service.get_memory(current_user, employee_id, memory_id)
    except (EmployeeError, MemoryError) as exc:
        raise _to_http_exception(exc)
    return MemoryResponse.model_validate(memory)


@router.delete(
    "/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a single memory for one of the user's employees",
    responses=_MEMORY_ITEM_RESPONSES,
)
def delete_memory(
    employee_id: uuid.UUID,
    memory_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> None:
    """Delete a single memory by id, scoped to the employee and user.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_memory(current_user, employee_id, memory_id)
    except (EmployeeError, MemoryError) as exc:
        raise _to_http_exception(exc)


@router.patch(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update a single memory for one of the user's employees",
    responses=_MEMORY_ITEM_RESPONSES,
)
def update_memory(
    employee_id: uuid.UUID,
    memory_id: uuid.UUID,
    data: MemoryUpdate,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> MemoryResponse:
    """Partially update a memory by id, scoped to the employee and user.

    Only the fields supplied in the body are changed; at least one field is
    required (an empty update yields ``422``). Same ``404``/``403``/``422``
    ownership and validation rules as the other single-memory endpoints.
    """
    try:
        memory = service.update_memory(
            current_user, employee_id, memory_id, data
        )
    except (EmployeeError, MemoryError) as exc:
        raise _to_http_exception(exc)
    return MemoryResponse.model_validate(memory)
