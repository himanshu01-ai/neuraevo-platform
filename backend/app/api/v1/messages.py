"""Message API endpoints (nested under a conversation).

Messages are immutable, so only create/list/get/delete are exposed.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUserDep, MessageServiceDep
from app.schemas.message import MessageCreate, MessageResponse
from app.services.conversation_service import (
    ConversationError,
    ConversationNotFoundError,
)
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeError,
    EmployeeNotFoundError,
)
from app.services.message_service import (
    MessageError,
    MessageNotFoundError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/conversations/{conversation_id}/messages",
    tags=["Messages"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": (
            "The employee, conversation, or message does not exist."
        )
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
    (MessageNotFoundError, status.HTTP_404_NOT_FOUND, "Message not found."),
]

_DomainError = EmployeeError | ConversationError | MessageError


def _to_http_exception(exc: _DomainError) -> HTTPException:
    for exc_type, code, detail in _DOMAIN_HTTP_MAP:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=code, detail=detail)
    # Defensive: an unmapped domain error should not be swallowed.
    raise exc


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a message to a conversation",
    responses=_RESPONSES,
)
def create_message(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    data: MessageCreate,
    current_user: CurrentUserDep,
    service: MessageServiceDep,
) -> MessageResponse:
    """Create a message in the conversation.

    The employee and conversation must belong to the authenticated user
    (``404``/``403``). ``role`` must be a valid role and ``content`` must be
    non-empty after trimming (``422`` otherwise).
    """
    try:
        message = service.create_message(
            current_user, employee_id, conversation_id, data
        )
    except (EmployeeError, ConversationError, MessageError) as exc:
        raise _to_http_exception(exc)
    return MessageResponse.model_validate(message)


@router.get(
    "",
    response_model=List[MessageResponse],
    summary="List a conversation's messages",
    responses=_RESPONSES,
)
def list_messages(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MessageServiceDep,
) -> List[MessageResponse]:
    """List the conversation's messages, ordered oldest to newest."""
    try:
        messages = service.list_messages(
            current_user, employee_id, conversation_id
        )
    except (EmployeeError, ConversationError, MessageError) as exc:
        raise _to_http_exception(exc)
    return [MessageResponse.model_validate(m) for m in messages]


@router.get(
    "/{message_id}",
    response_model=MessageResponse,
    summary="Get a single message",
    responses=_RESPONSES,
)
def get_message(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MessageServiceDep,
) -> MessageResponse:
    """Return a single message by id, scoped to the conversation.

    Returns ``404`` if it does not exist or belongs to a different
    conversation. Invalid path UUIDs yield ``422``.
    """
    try:
        message = service.get_message(
            current_user, employee_id, conversation_id, message_id
        )
    except (EmployeeError, ConversationError, MessageError) as exc:
        raise _to_http_exception(exc)
    return MessageResponse.model_validate(message)


@router.delete(
    "/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message",
    responses=_RESPONSES,
)
def delete_message(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: MessageServiceDep,
) -> None:
    """Delete a message by id, scoped to the conversation.

    Returns ``204 No Content`` on success. Same ``404``/``403``/``422`` rules
    as the GET endpoint.
    """
    try:
        service.delete_message(
            current_user, employee_id, conversation_id, message_id
        )
    except (EmployeeError, ConversationError, MessageError) as exc:
        raise _to_http_exception(exc)
