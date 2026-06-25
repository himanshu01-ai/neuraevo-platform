"""Blueprint generation API (preview/foundation).

A non-persisting preview of blueprint generation. Kept in its own router so the
completed Sprint 3A blueprint CRUD endpoints are not modified.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    BlueprintGenerationServiceDep,
    CurrentUserDep,
)
from app.schemas.blueprint_generation import BlueprintGenerationPreviewResponse
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintError,
    BlueprintNotFoundError,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/blueprint/generate",
    tags=["Blueprint Generation"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee or blueprint does not exist."
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
]


def _to_http_exception(exc: EmployeeError | BlueprintError) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    raise exc


@router.post(
    "/preview",
    response_model=BlueprintGenerationPreviewResponse,
    summary="Preview blueprint generation from interview data (no persistence)",
    responses=_RESPONSES,
)
def preview_blueprint_generation(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: BlueprintGenerationServiceDep,
) -> BlueprintGenerationPreviewResponse:
    """Aggregate interview data and return a generated draft blueprint.

    Read-only: nothing is written to the database (``metadata.persisted`` is
    always ``false``). Requires the employee and its blueprint to belong to the
    authenticated user (``404``/``403``); invalid path UUIDs yield ``422``.
    """
    try:
        return service.preview_generation(current_user, employee_id)
    except (EmployeeError, BlueprintError) as exc:
        raise _to_http_exception(exc)
