"""Conversation generation API.

Generates the next assistant reply, persists it as a message (Sprint 5E), and
returns the stored message. Kept in its own router so completed
conversation/message endpoints are not modified.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.rate_limit import enforce_ai_rate_limit

from app.core.dependencies import (
    ConversationGenerationServiceDep,
    CurrentUserDep,
)
from app.schemas.message import MessageResponse
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
from app.services.providers.conversation_provider import (
    ConversationGenerationError,
    ConversationGenerationTimeoutError,
)

router = APIRouter(
    prefix="/employees/{employee_id}/conversations/{conversation_id}/generate",
    tags=["Conversation Generation"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, conversation, or blueprint does not exist."
    },
    status.HTTP_502_BAD_GATEWAY: {
        "description": "The AI provider failed to generate a reply."
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


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate the next assistant reply and store it as a message",
    dependencies=[Depends(enforce_ai_rate_limit)],
    responses=_RESPONSES,
)
def generate_conversation_reply(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationGenerationServiceDep,
) -> MessageResponse:
    """Generate the next assistant reply, persist it, and return the message.

    Generates from the blueprint and conversation history, then stores exactly
    one assistant message and returns it. Requires the employee, its blueprint,
    and the conversation to belong to the authenticated user (``404``/``403``);
    invalid path UUIDs yield ``422``. A generation failure (``502``/``504``)
    writes nothing.
    """
    try:
        message = service.generate_reply(
            current_user, employee_id, conversation_id
        )
    except (EmployeeError, BlueprintError, ConversationError) as exc:
        raise _to_http_exception(exc)
    except ConversationGenerationTimeoutError:
        # Do not leak Anthropic internals to the client.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Conversation generation timed out. Please try again.",
        )
    except ConversationGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Conversation generation failed. Please try again later.",
        )
    return MessageResponse.model_validate(message)
