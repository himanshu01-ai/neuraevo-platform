"""AI context API endpoint (read-only input builder)."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AIContextServiceDep, CurrentUserDep
from app.schemas.ai_context import AIContextResponse
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintError,
    BlueprintNotFoundError,
)
from app.services.conversation_service import (
    ConversationError,
    ConversationNotFoundError,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/conversations/{conversation_id}/ai-context",
    tags=["AI Context"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, blueprint, or conversation does not exist."
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
        ConversationNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Conversation not found.",
    ),
]


def _to_http_exception(
    exc: EmployeeError | BlueprintError | ConversationError,
) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.get(
    "",
    response_model=AIContextResponse,
    summary="Assemble the complete AI context for an employee conversation",
    responses=_RESPONSES,
)
def get_ai_context(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: AIContextServiceDep,
) -> AIContextResponse:
    """Return the combined blueprint, memory, and conversation context.

    Read-only: nothing is written. The employee, its blueprint, and the
    conversation must belong to the authenticated user (``404``/``403``);
    invalid path UUIDs yield ``422``.
    """
    try:
        return service.build_ai_context(
            current_user, employee_id, conversation_id
        )
    except (EmployeeError, BlueprintError, ConversationError) as exc:
        raise _to_http_exception(exc)
