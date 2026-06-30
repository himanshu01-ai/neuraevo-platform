"""Memory context API endpoint (read-only assembly)."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, MemoryContextServiceDep
from app.schemas.memory_context import MemoryContextResponse
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/memory-context",
    tags=["Memory Context"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
}

_DOMAIN_HTTP_MAP: list[tuple[type[Exception], int, str]] = [
    (EmployeeNotFoundError, status.HTTP_404_NOT_FOUND, "Employee not found."),
    (
        EmployeeAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this employee.",
    ),
]


def _to_http_exception(exc: EmployeeError) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.get(
    "",
    response_model=MemoryContextResponse,
    summary="Assemble an employee's memories into a context structure",
    responses=_RESPONSES,
)
def get_memory_context(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MemoryContextServiceDep,
) -> MemoryContextResponse:
    """Return the employee's memories assembled as context, newest first.

    The employee must belong to the authenticated user (``404``/``403``). An
    employee with no memories returns ``memory_count = 0`` with an empty list
    (``200``). Invalid path UUIDs yield ``422``.
    """
    try:
        return service.build_memory_context(current_user, employee_id)
    except EmployeeError as exc:
        raise _to_http_exception(exc)
