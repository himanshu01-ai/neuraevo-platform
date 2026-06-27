"""Conversation API endpoints (nested under an employee)."""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import ConversationServiceDep, CurrentUserDep
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
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
    prefix="/employees/{employee_id}/conversations", tags=["Conversations"]
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


def _to_http_exception(
    exc: EmployeeError | ConversationError,
) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation for the authenticated user's employee",
    responses=_RESPONSES,
)
def create_conversation(
    employee_id: uuid.UUID,
    data: ConversationCreate,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    """Create a conversation. ``status`` defaults to ``active``.

    The employee must belong to the authenticated user (``404``/``403``).
    """
    try:
        conversation = service.create_conversation(
            current_user, employee_id, data
        )
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
    return ConversationResponse.model_validate(conversation)


@router.get(
    "",
    response_model=List[ConversationResponse],
    summary="List the employee's conversations",
    responses=_RESPONSES,
)
def list_conversations(
    employee_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> List[ConversationResponse]:
    """List the employee's conversations, ordered by created_at ascending."""
    try:
        conversations = service.list_conversations(current_user, employee_id)
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
    return [ConversationResponse.model_validate(conv) for conv in conversations]


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a single conversation",
    responses=_RESPONSES,
)
def get_conversation(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    """Return a single conversation by id, scoped to the employee.

    Returns ``404`` if it does not exist or belongs to a different employee.
    Invalid path UUIDs yield ``422``.
    """
    try:
        conversation = service.get_conversation(
            current_user, employee_id, conversation_id
        )
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
    return ConversationResponse.model_validate(conversation)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update a conversation's title and/or status",
    responses=_RESPONSES,
)
def update_conversation(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationResponse:
    """Update a conversation's ``title`` and/or ``status``.

    Only supplied fields change. Invalid ``status`` values yield ``422``; same
    ``404``/``403`` ownership rules as the other endpoints.
    """
    try:
        conversation = service.update_conversation(
            current_user, employee_id, conversation_id, data
        )
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
    return ConversationResponse.model_validate(conversation)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
    responses=_RESPONSES,
)
def delete_conversation(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> None:
    """Delete a conversation by id, scoped to the employee.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_conversation(current_user, employee_id, conversation_id)
    except (EmployeeError, ConversationError) as exc:
        raise _to_http_exception(exc)
