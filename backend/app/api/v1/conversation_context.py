"""Conversation context API endpoint (read-only assembly)."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    ConversationContextServiceDep,
    CurrentUserDep,
)
from app.schemas.conversation_context import ConversationContextResponse
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
    prefix="/employees/{employee_id}/conversations/{conversation_id}/context",
    tags=["Conversation Context"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee or conversation does not exist."
    },
}

_DOMAIN_HTTP_MAP: list[tuple[type[Exception], int, str]] = [
    (EmployeeNotFoundError, status.HTTP_404_NOT_FOUND, "Employee not found."),
    (
        EmployeeAccessDeniedError,
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this employee.",
    ),
    (
        ConversationNotFoundError,
        status.HTTP_404_NOT_FOUND,
        "Conversation not found.",
    ),
]


def _to_http_exception(exc: EmployeeError | ConversationError) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.get(
    "",
    response_model=ConversationContextResponse,
    summary="Assemble a conversation's history into a context structure",
    responses=_RESPONSES,
)
def get_conversation_context(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationContextServiceDep,
) -> ConversationContextResponse:
    """Return the conversation's messages assembled as context, oldest first.

    The employee and conversation must belong to the authenticated user
    (``404``/``403``). An empty conversation returns ``message_count = 0`` with
    an empty list (``200``). Invalid path UUIDs yield ``422``.
    """
    try:
        return service.build_context(
            current_user, employee_id, conversation_id
        )
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
