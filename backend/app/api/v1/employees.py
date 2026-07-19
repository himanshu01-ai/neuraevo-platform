"""Employee API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import CurrentUserDep, EmployeeServiceDep
from app.schemas.employee import (
    EmployeeActivityResponse,
    EmployeeAssignmentCreate,
    EmployeeAssignmentResponse,
    EmployeeCapabilityInput,
    EmployeeCreate,
    EmployeeHealthResponse,
    EmployeePermissionResponse,
    EmployeeResponse,
    EmployeeRestoreRequest,
    EmployeeUpdate,
)
from app.services.employee_health import derive_health
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
    EmployeeValidationError,
    InvalidStatusTransitionError,
)
from app.utils.constants import EmployeeCapability

router = APIRouter(prefix="/employees", tags=["Employees"])

_OWNERSHIP_RESPONSES = {
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
}


def _to_http_exception(exc: Exception) -> HTTPException:
    """Translate a domain error into its HTTP equivalent.

    One place so every endpoint maps the same error to the same status.
    """
    if isinstance(exc, EmployeeNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )
    if isinstance(exc, EmployeeAccessDeniedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this employee.",
        )
    if isinstance(exc, InvalidStatusTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        )
    if isinstance(exc, EmployeeValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    raise exc


def _to_response(employee, service) -> EmployeeResponse:
    """Build the public representation, including the derived fields.

    Constructed field by field rather than via ``model_validate``: the ORM's
    ``capabilities`` and ``permissions`` are collections of *grant rows*, not
    the flat values the response exposes, so attribute-based validation would
    hand pydantic the wrong shape. Flattening them here keeps the wire contract
    independent of how the grants are stored.
    """
    return EmployeeResponse(
        id=employee.id,
        user_id=employee.user_id,
        name=employee.name,
        role=employee.role,
        description=employee.description,
        language=employee.language,
        personality=employee.personality,
        status=employee.status,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
        autonomy=employee.autonomy,
        tone=employee.tone,
        execution_mode=employee.execution_mode,
        priority=employee.priority,
        require_approval=employee.require_approval,
        accent=employee.accent,
        glyph=employee.glyph,
        archived_at=employee.archived_at,
        health=derive_health(employee).state,
        capabilities=[
            EmployeeCapability(grant.capability) for grant in employee.capabilities
        ],
        permissions=[
            EmployeePermissionResponse(
                permission=grant.permission, level=grant.level
            )
            for grant in employee.permissions
        ],
        assignment_count=service.assignment_count(employee),
    )


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
    never from the request body. Configuration, capabilities and permissions
    are optional — omitting them creates an employee with the defaults.
    """
    try:
        employee = service.create_employee(current_user, data)
    except EmployeeValidationError as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


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
    returned, deleted employees are excluded, and an empty list is returned if
    they have none.
    """
    employees = service.list_employees(current_user)
    return [_to_response(e, service) for e in employees]


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Get one of the authenticated user's employees",
    responses=_OWNERSHIP_RESPONSES,
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
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update one of the authenticated user's employees",
    responses=_OWNERSHIP_RESPONSES,
)
def update_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Apply a partial update.

    Only supplied fields change. A disallowed status transition yields ``409``;
    a permission granted without its capability yields ``422``.
    """
    try:
        employee = service.update_employee(current_user, employee_id, data)
    except (
        EmployeeNotFoundError,
        EmployeeAccessDeniedError,
        InvalidStatusTransitionError,
        EmployeeValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's employees",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_employee(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> Response:
    """Delete an employee.

    This is a soft delete: the employee disappears from every read path while
    its memories, blueprint, interview sessions and conversations are retained.
    """
    try:
        service.delete_employee(current_user, employee_id)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{employee_id}/archive",
    response_model=EmployeeResponse,
    summary="Archive an employee",
    responses=_OWNERSHIP_RESPONSES,
)
def archive_employee(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Take an employee out of service without destroying it."""
    try:
        employee = service.archive_employee(current_user, employee_id)
    except (
        EmployeeNotFoundError,
        EmployeeAccessDeniedError,
        InvalidStatusTransitionError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.post(
    "/{employee_id}/restore",
    response_model=EmployeeResponse,
    summary="Restore an archived employee",
    responses=_OWNERSHIP_RESPONSES,
)
def restore_employee(
    employee_id: uuid.UUID,
    data: EmployeeRestoreRequest,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Bring an archived employee back to ``draft`` or ``ready``."""
    try:
        employee = service.restore_employee(current_user, employee_id, data.status)
    except (
        EmployeeNotFoundError,
        EmployeeAccessDeniedError,
        InvalidStatusTransitionError,
    ) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.get(
    "/{employee_id}/activity",
    response_model=List[EmployeeActivityResponse],
    summary="List an employee's activity history",
    responses=_OWNERSHIP_RESPONSES,
)
def list_activity(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> List[EmployeeActivityResponse]:
    """Return recorded events for one employee, newest first."""
    try:
        events = service.list_activity(
            current_user, employee_id, skip=skip, limit=limit
        )
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return [EmployeeActivityResponse.model_validate(e) for e in events]


@router.get(
    "/{employee_id}/capabilities",
    response_model=List[EmployeeCapability],
    summary="List the capabilities an employee holds",
    responses=_OWNERSHIP_RESPONSES,
)
def list_capabilities(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> List[EmployeeCapability]:
    try:
        return service.list_capabilities(current_user, employee_id)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)


@router.post(
    "/{employee_id}/capabilities",
    response_model=EmployeeResponse,
    summary="Grant a capability to an employee",
    responses=_OWNERSHIP_RESPONSES,
)
def add_capability(
    employee_id: uuid.UUID,
    data: EmployeeCapabilityInput,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    try:
        employee = service.add_capability(current_user, employee_id, data.capability)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.delete(
    "/{employee_id}/capabilities/{capability}",
    response_model=EmployeeResponse,
    summary="Revoke a capability from an employee",
    responses=_OWNERSHIP_RESPONSES,
)
def remove_capability(
    employee_id: uuid.UUID,
    capability: EmployeeCapability,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeResponse:
    """Revoke a capability.

    Permissions that depended on it drop to ``blocked`` in the same
    transaction, so the employee is never left holding a permission it cannot
    exercise.
    """
    try:
        employee = service.remove_capability(current_user, employee_id, capability)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return _to_response(employee, service)


@router.get(
    "/{employee_id}/assignments",
    response_model=List[EmployeeAssignmentResponse],
    summary="List the work an employee is assigned to",
    responses=_OWNERSHIP_RESPONSES,
)
def list_assignments(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> List[EmployeeAssignmentResponse]:
    try:
        assignments = service.list_assignments(current_user, employee_id)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return [EmployeeAssignmentResponse.model_validate(a) for a in assignments]


@router.post(
    "/{employee_id}/assignments",
    response_model=EmployeeAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an employee to a piece of work",
    responses=_OWNERSHIP_RESPONSES,
)
def create_assignment(
    employee_id: uuid.UUID,
    data: EmployeeAssignmentCreate,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeAssignmentResponse:
    """Record that an employee is expected to work on something.

    Assignment is a description — nothing here schedules, orders, or runs the
    work.
    """
    try:
        assignment = service.assign_work(current_user, employee_id, data)
    except (
        EmployeeNotFoundError,
        EmployeeAccessDeniedError,
        EmployeeValidationError,
    ) as exc:
        raise _to_http_exception(exc)
    return EmployeeAssignmentResponse.model_validate(assignment)


@router.delete(
    "/{employee_id}/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unassign an employee from a piece of work",
    responses=_OWNERSHIP_RESPONSES,
)
def delete_assignment(
    employee_id: uuid.UUID,
    assignment_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> Response:
    try:
        service.unassign_work(current_user, employee_id, assignment_id)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{employee_id}/health",
    response_model=EmployeeHealthResponse,
    summary="Report an employee's health",
    responses=_OWNERSHIP_RESPONSES,
)
def get_health(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: EmployeeServiceDep,
) -> EmployeeHealthResponse:
    """Report health derived from stored configuration.

    Nothing here is sampled or measured — every answer follows from facts
    already in the database, and the reasons name which ones.
    """
    try:
        employee = service.get_employee(current_user, employee_id)
    except (EmployeeNotFoundError, EmployeeAccessDeniedError) as exc:
        raise _to_http_exception(exc)

    report = derive_health(employee)
    return EmployeeHealthResponse(
        employee_id=employee.id,
        status=employee.status,
        health=report.state,
        reasons=report.reasons,
    )

