"""Blueprint generation API.

Hosts the non-persisting ``/preview`` (Sprint 4A/4B) and the persisting
``/apply`` (Sprint 4C) generation endpoints. Kept in its own router so the
completed Sprint 3A blueprint CRUD endpoints are not modified.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.rate_limit import enforce_ai_rate_limit

from app.core.dependencies import (
    BlueprintApplyServiceDep,
    BlueprintGenerationServiceDep,
    CurrentUserDep,
)
from app.employee_builder.blueprint import (
    BlueprintGenerationError,
    BlueprintGenerationTimeoutError,
)
from app.schemas.blueprint import BlueprintResponse
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
    status.HTTP_502_BAD_GATEWAY: {
        "description": "The AI provider failed to generate a blueprint."
    },
    status.HTTP_504_GATEWAY_TIMEOUT: {
        "description": "The AI provider timed out."
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
    dependencies=[Depends(enforce_ai_rate_limit)],
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
    except BlueprintGenerationTimeoutError:
        # Do not leak Anthropic internals to the client.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Blueprint generation timed out. Please try again.",
        )
    except BlueprintGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blueprint generation failed. Please try again later.",
        )


@router.post(
    "/apply",
    response_model=BlueprintResponse,
    summary="Generate a blueprint and persist it to the employee's blueprint",
    dependencies=[Depends(enforce_ai_rate_limit)],
    responses=_RESPONSES,
)
def apply_blueprint_generation(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: BlueprintApplyServiceDep,
) -> BlueprintResponse:
    """Generate a draft and persist it, returning the updated blueprint.

    Unlike ``/preview``, this commits the generated values to the blueprint.
    Only non-null draft fields overwrite existing values; ``id``,
    ``employee_id``, and ``created_at`` are never modified. Same ownership
    (``404``/``403``), validation (``422``), and generation (``502``/``504``)
    semantics as ``/preview``.
    """
    try:
        blueprint = service.apply_generation(current_user, employee_id)
    except (EmployeeError, BlueprintError) as exc:
        raise _to_http_exception(exc)
    except BlueprintGenerationTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Blueprint generation timed out. Please try again.",
        )
    except BlueprintGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blueprint generation failed. Please try again later.",
        )
    return BlueprintResponse.model_validate(blueprint)
