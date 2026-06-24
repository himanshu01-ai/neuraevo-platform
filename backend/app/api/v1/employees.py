"""Employee API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, EmployeeServiceDep
from app.schemas.employee import EmployeeCreate, EmployeeResponse
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI employee for the authenticated user",
)
def create_employee(
    data: EmployeeCreate,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Create an employee and attach it to the authenticated user.

    Requires a valid Bearer access token; the owner is taken from the token,
    never from the request body.
    """
    employee = service.create_employee(current_user, data)
    return EmployeeResponse.model_validate(employee)


@router.get(
    "",
    response_model=List[EmployeeResponse],
    summary="List the authenticated user's employees",
)
def list_employees(
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> List[EmployeeResponse]:
    """Return every employee owned by the authenticated user.

    Requires a valid Bearer access token. Only the caller's own employees are
    returned; an empty list is returned if they have none.
    """
    employees = service.list_employees(current_user)
    return [EmployeeResponse.model_validate(e) for e in employees]


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get one of the authenticated user's employees",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "The employee belongs to another user."
        },
        status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
    },
)
def get_employee(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Return a single employee by id, scoped to the authenticated user.

    Returns ``404`` if no employee with that id exists, and ``403`` if it
    exists but is owned by a different user.
    """
    try:
        employee = service.get_employee(current_user, employee_id)
    except EmployeeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )
    except EmployeeAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this employee.",
        )
    return EmployeeResponse.model_validate(employee)
