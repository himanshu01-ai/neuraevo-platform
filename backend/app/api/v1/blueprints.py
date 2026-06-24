"""Blueprint API endpoints (nested under an employee).

Each employee has at most one blueprint, so these endpoints address the
singular ``/blueprint`` sub-resource without a blueprint id in the path.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import BlueprintServiceDep, CurrentUserDep
from app.schemas.blueprint import (
    BlueprintCreate,
    BlueprintResponse,
    BlueprintUpdate,
)
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintAlreadyExistsError,
    BlueprintError,
    BlueprintNotFoundError,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)

router = APIRouter(prefix="/employees/{employee_id}/blueprint", tags=["Blueprints"])

# Shared documented responses. 422 (invalid UUID) is added automatically.
_READ_WRITE_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee or blueprint does not exist."
    },
}

_CREATE_RESPONSES = {
    **_READ_WRITE_RESPONSES,
    status.HTTP_409_CONFLICT: {
        "description": "The employee already has a blueprint."
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
    (BlueprintNotFoundError, status.HTTP_404_NOT_FOUND, "Blueprint not found."),
    (
        BlueprintAlreadyExistsError,
        status.HTTP_409_CONFLICT,
        "This employee already has a blueprint.",
    ),
    (
        BlueprintAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this blueprint.",
    ),
]


def _to_http_exception(exc: EmployeeError | BlueprintError) -> HTTPException:
    """Translate an ownership/lookup domain error into an HTTPException."""
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=BlueprintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the blueprint for one of the user's employees",
    responses=_CREATE_RESPONSES,
)
def create_blueprint(
    employee_id: uuid.UUID,
    data: BlueprintCreate,
    current_user: CurrentUserDep,
    service: BlueprintServiceDep,
) -> BlueprintResponse:
    """Create the employee's single blueprint.

    Returns ``409`` if the employee already has one, ``404``/``403`` for the
    employee ownership chain, and ``422`` for invalid input.
    """
    try:
        blueprint = service.create_blueprint(current_user, employee_id, data)
    except (EmployeeError, BlueprintError) as exc:
        raise _to_http_exception(exc)
    return BlueprintResponse.model_validate(blueprint)


@router.get(
    "",
    response_model=BlueprintResponse,
    summary="Get the blueprint for one of the user's employees",
    responses=_READ_WRITE_RESPONSES,
)
def get_blueprint(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: BlueprintServiceDep,
) -> BlueprintResponse:
    """Return the employee's blueprint, or ``404`` if it has none."""
    try:
        blueprint = service.get_blueprint(current_user, employee_id)
    except (EmployeeError, BlueprintError) as exc:
        raise _to_http_exception(exc)
    return BlueprintResponse.model_validate(blueprint)


@router.patch(
    "",
    response_model=BlueprintResponse,
    summary="Update the blueprint for one of the user's employees",
    responses=_READ_WRITE_RESPONSES,
)
def update_blueprint(
    employee_id: uuid.UUID,
    data: BlueprintUpdate,
    current_user: CurrentUserDep,
    service: BlueprintServiceDep,
) -> BlueprintResponse:
    """Partially update the employee's blueprint.

    Only supplied fields are changed. Returns ``404`` if the employee has no
    blueprint, ``404``/``403`` for the employee ownership chain.
    """
    try:
        blueprint = service.update_blueprint(current_user, employee_id, data)
    except (EmployeeError, BlueprintError) as exc:
        raise _to_http_exception(exc)
    return BlueprintResponse.model_validate(blueprint)
