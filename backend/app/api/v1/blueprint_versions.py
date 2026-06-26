"""Blueprint version (history) API endpoints (read-only).

Exposes the historical snapshots captured by the apply workflow. Kept in its
own router so completed blueprint CRUD/generation modules are not modified.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import BlueprintVersionServiceDep, CurrentUserDep
from app.schemas.blueprint_version import BlueprintVersionResponse
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintError,
    BlueprintNotFoundError,
)
from app.services.blueprint_version_service import (
    BlueprintVersionError,
    BlueprintVersionNotFoundError,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/blueprint/versions",
    tags=["Blueprint Versions"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, blueprint, or version does not exist."
    },
}

_DOMAIN_HTTP_MAP: list[tuple[type[Exception], int, str]] = [
    (EmployeeNotFoundError, status.HTTP_404_NOT_FOUND, "Employee not found."),
    (
        EmployeeAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this employee.",
    ),
    (BlueprintNotFoundError, status.HTTP_404_NOT_FOUND, "Blueprint not found."),
    (
        BlueprintAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this blueprint.",
    ),
    (
        BlueprintVersionNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Blueprint version not found.",
    ),
]


def _to_http_exception(
    exc: EmployeeError | BlueprintError | BlueprintVersionError,
) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    raise exc


@router.get(
    "",
    response_model=List[BlueprintVersionResponse],
    summary="List the version history for an employee's blueprint",
    responses=_RESPONSES,
)
def list_blueprint_versions(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: BlueprintVersionServiceDep,
) -> List[BlueprintVersionResponse]:
    """List the blueprint's version snapshots, oldest first.

    The employee must belong to the authenticated user (``404``/``403``).
    Returns an empty list if the blueprint has no history yet.
    """
    try:
        versions = service.list_versions(current_user, employee_id)
    except (EmployeeError, BlueprintError, BlueprintVersionError) as exc:
        raise _to_http_exception(exc)
    return [BlueprintVersionResponse.model_validate(v) for v in versions]


@router.get(
    "/{version_id}",
    response_model=BlueprintVersionResponse,
    summary="Get a single blueprint version snapshot",
    responses=_RESPONSES,
)
def get_blueprint_version(
    employee_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: BlueprintVersionServiceDep,
) -> BlueprintVersionResponse:
    """Return a single version snapshot by id, scoped to the blueprint.

    Returns ``404`` if the version does not exist or belongs to a different
    blueprint. Invalid path UUIDs yield ``422``.
    """
    try:
        version = service.get_version(current_user, employee_id, version_id)
    except (EmployeeError, BlueprintError, BlueprintVersionError) as exc:
        raise _to_http_exception(exc)
    return BlueprintVersionResponse.model_validate(version)
