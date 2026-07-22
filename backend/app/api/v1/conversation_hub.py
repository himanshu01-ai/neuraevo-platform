"""Conversation Hub API — conversations as the platform interaction layer (Sprint 21).

Makes a conversation addressable by its own id, across any of the user's
employees, and adds the channel-aware *turn* endpoint that text and voice both
run through. Existing employee-scoped conversation endpoints are unchanged, so
nothing here is a breaking change:

    GET    /conversations                    the user's conversations (all employees)
    POST   /conversations                    start one with an employee
    GET    /conversations/{id}               one conversation's header
    PATCH  /conversations/{id}               rename / archive / restore
    DELETE /conversations/{id}               delete
    GET    /conversations/{id}/messages       its messages (the transcript)
    POST   /conversations/{id}/turn           one exchange: says X (text|voice) → reply

Ownership is the reused Employee chain; the router only translates HTTP. A
spoken turn is a transcript with ``channel=voice`` — speech recognition and
synthesis are the browser's, never the server's.
"""

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    ConversationActionServiceDep,
    ConversationServiceDep,
    ConversationTurnServiceDep,
    CurrentUserDep,
    MessageServiceDep,
)
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationUpdate
from app.schemas.conversation_hub import (
    ConversationActionRequest,
    ConversationActionResponse,
    ConversationHubCreate,
    ConversationListResponse,
    ConversationSummaryResponse,
    ConversationTurnRequest,
    ConversationTurnResponse,
)
from app.schemas.conversation import ConversationCreate
from app.schemas.message import MessageResponse
from app.services.blueprint_service import (
    BlueprintAccessDeniedError,
    BlueprintNotFoundError,
)
from app.services.conversation_service import ConversationNotFoundError
from app.services.employee_service import (
    EmployeeAccessDeniedError,
    EmployeeNotFoundError,
)
from app.services.providers.conversation_provider import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)

router = APIRouter(prefix="/conversations", tags=["Conversation Hub"])

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_404_NOT_FOUND: {"description": "The conversation does not exist."},
}

_CREATE_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {"description": "The employee belongs to another user."},
    status.HTTP_404_NOT_FOUND: {"description": "The employee does not exist."},
}

_TURN_RESPONSES = {
    **_RESPONSES,
    status.HTTP_404_NOT_FOUND: {
        "description": "The conversation or the employee's blueprint does not exist."
    },
    status.HTTP_502_BAD_GATEWAY: {
        "description": "The AI provider failed to generate a reply."
    },
    status.HTTP_504_GATEWAY_TIMEOUT: {"description": "The AI provider timed out."},
}


def _summary(
    conversation: Conversation,
    employee_name: str,
    message_count: int,
    last_message: str | None,
) -> ConversationSummaryResponse:
    return ConversationSummaryResponse(
        id=conversation.id,
        employee_id=conversation.employee_id,
        employee_name=employee_name,
        title=conversation.title,
        status=conversation.status,
        message_count=message_count,
        last_message=last_message,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List the authenticated user's conversations across all employees",
    responses={status.HTTP_401_UNAUTHORIZED: _RESPONSES[status.HTTP_401_UNAUTHORIZED]},
)
def list_conversations(
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationListResponse:
    """Return the user's conversations, newest first, with the total.

    Each carries its owning employee, message count, and last line, so the
    sidebar renders without a follow-up request per conversation. An empty list
    when the user has none.
    """
    rows = service.list_for_user(current_user)
    items = [
        _summary(conversation, name, count, last)
        for conversation, name, count, last in rows
    ]
    return ConversationListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=ConversationSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a conversation with one of the user's employees",
    responses=_CREATE_RESPONSES,
)
def create_conversation(
    data: ConversationHubCreate,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationSummaryResponse:
    """Create a conversation for the given employee and return its header.

    The employee must belong to the authenticated user (``404``/``403``). A new
    conversation opens ``active`` with no messages.
    """
    try:
        conversation = service.create_conversation(
            current_user,
            data.employee_id,
            ConversationCreate(title=data.title),
        )
    except EmployeeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found."
        )
    except EmployeeAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this employee.",
        )
    name, count, last = service.overview_of(conversation)
    return _summary(conversation, name, count, last)


@router.get(
    "/{conversation_id}",
    response_model=ConversationSummaryResponse,
    summary="Get one of the user's conversations",
    responses=_RESPONSES,
)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationSummaryResponse:
    """Return a single conversation's header, addressed by its id."""
    try:
        conversation = service.get_for_user(current_user, conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    name, count, last = service.overview_of(conversation)
    return _summary(conversation, name, count, last)


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummaryResponse,
    summary="Rename or archive/restore one of the user's conversations",
    responses=_RESPONSES,
)
def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> ConversationSummaryResponse:
    """Partially update a conversation. Only supplied fields change."""
    try:
        conversation = service.update_for_user(current_user, conversation_id, data)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    name, count, last = service.overview_of(conversation)
    return _summary(conversation, name, count, last)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the user's conversations",
    responses=_RESPONSES,
)
def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
) -> None:
    """Delete a conversation and its messages, addressed by its id."""
    try:
        service.delete_for_user(current_user, conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )


@router.get(
    "/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="List a conversation's messages (the transcript)",
    responses=_RESPONSES,
)
def list_messages(
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationServiceDep,
    messages: MessageServiceDep,
) -> List[MessageResponse]:
    """Return the conversation's messages, oldest first — text and voice alike.

    Each message carries its ``channel``, so a client can show which turns were
    spoken and re-speak the assistant's replies.
    """
    try:
        conversation = service.get_for_user(current_user, conversation_id)
        rows = messages.list_messages(
            current_user, conversation.employee_id, conversation_id
        )
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    return [MessageResponse.model_validate(row) for row in rows]


@router.post(
    "/{conversation_id}/turn",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run one conversation turn (text or voice) and get both messages",
    responses=_TURN_RESPONSES,
)
def run_turn(
    conversation_id: uuid.UUID,
    data: ConversationTurnRequest,
    current_user: CurrentUserDep,
    service: ConversationTurnServiceDep,
) -> ConversationTurnResponse:
    """Persist the human message, generate the reply, and return both.

    The channel (``text`` or ``voice``) is recorded on both messages, so a voice
    exchange reads as one in the transcript. A spoken turn arrives here as its
    transcript — the platform never handles audio. Ownership of the conversation
    (``404``), the employee's blueprint (``404``), and provider failures
    (``502``/``504``) surface exactly as the existing generation endpoint's do;
    a failed reply leaves the human message saved, so a retry re-generates.
    """
    try:
        user_message, assistant_message = service.run_turn(
            current_user,
            conversation_id,
            data.content,
            channel=data.channel,
        )
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    except (BlueprintNotFoundError, BlueprintAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This employee has no blueprint yet, so it can't reply.",
        )
    except ConversationGenerationTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The reply timed out. Your message was saved — try again.",
        )
    except ConversationGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The reply couldn't be generated. Your message was saved — try again.",
        )
    return ConversationTurnResponse(
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )


@router.post(
    "/{conversation_id}/actions",
    response_model=ConversationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Carry out a confirmed conversation action (creates a linked task)",
    responses=_RESPONSES,
)
def create_conversation_action(
    conversation_id: uuid.UUID,
    data: ConversationActionRequest,
    current_user: CurrentUserDep,
    service: ConversationActionServiceDep,
) -> ConversationActionResponse:
    """Turn a user-approved action into a real task carried by the employee.

    Called after the user confirms an action the assistant proposed. The task
    is created by the one Task Engine, carried by the conversation's employee,
    recorded on both the task's and the conversation's timelines, and announced
    in the owner's inbox — so work started in a conversation lands in the
    workspace and is visible everywhere, rather than being a detached call. The
    conversation must belong to the caller (``404``); the confirmation itself is
    the client's, upheld before this endpoint is reached.
    """
    try:
        task = service.create_task_from_conversation(
            current_user,
            conversation_id,
            data.label,
            data.summary,
        )
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )
    return ConversationActionResponse(
        task_id=task.id,
        business_id=task.business_id,
        name=task.name,
        status=task.status,
        employee_id=task.employee_id,
    )
