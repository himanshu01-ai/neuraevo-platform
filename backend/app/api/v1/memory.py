"""Memory API endpoints (nested under an employee)."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, MemoryServiceDep
from app.schemas.memory import MemoryCreate, MemoryResponse
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
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
    responses=_OWNERSHIP_RESPONSES,
)
def list_memories(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryServiceDep,
) -> List[MemoryResponse]:
    """List all memories for the given employee, oldest first.

    The employee must belong to the authenticated user (``404``/``403`` as
    above). Returns an empty list if the employee has no memories.
    """
    try:
        memories = service.list_memories(current_user, employee_id)
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
