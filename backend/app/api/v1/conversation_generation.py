"""Conversation generation API (preview/foundation).

A non-persisting generation of the next assistant reply. Kept in its own
router so completed conversation/message endpoints are not modified.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    ConversationGenerationServiceDep,
    CurrentUserDep,
)
from app.schemas.conversation_generation import ConversationGenerationResponse
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
    response_model=ConversationGenerationResponse,
    summary="Generate the next assistant reply for a conversation (no persistence)",
    responses=_RESPONSES,
)
def generate_conversation_reply(
    employee_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user: CurrentUserDep,
    service: ConversationGenerationServiceDep,
) -> ConversationGenerationResponse:
    """Generate the next assistant reply from the blueprint and history.

    Read-only: nothing is written to the database. Requires the employee, its
    blueprint, and the conversation to belong to the authenticated user
    (``404``/``403``); invalid path UUIDs yield ``422``.
    """
    try:
        return service.generate_reply(
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
