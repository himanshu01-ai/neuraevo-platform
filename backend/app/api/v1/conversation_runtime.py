"""Conversation Runtime API (Sprint 7.5).

Exposes the Sprint 7.4 :class:`ConversationRuntimeService` — the single runtime
entry point for AI execution — through one POST endpoint.

The router is HTTP-only: it validates the request, delegates to the service, maps
domain errors to HTTP status codes, and returns the provider-agnostic
:class:`AIResponse`. It contains no business logic, builds no prompts, calls no
providers, and touches no repositories or ownership logic — all of that lives in
the coordinated services. Nothing is persisted (Sprint 7.5 stop point).
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import ConversationRuntimeServiceDep, CurrentUserDep
from app.schemas.ai_response import AIResponse
from app.schemas.conversation_runtime import GenerateConversationRequest
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
    prefix="/conversations/{conversation_id}/runtime",
    tags=["Conversation Runtime"],
)

_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid credentials."},
    status.HTTP_403_FORBIDDEN: {
        "description": "The employee belongs to another user."
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "The employee, blueprint, or conversation does not exist."
    },
    status.HTTP_502_BAD_GATEWAY: {
        "description": "The AI provider failed to generate a response."
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
    response_model=AIResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an AI response for an existing conversation (runtime pipeline)",
    responses=_RESPONSES,
)
def generate_runtime_response(
    conversation_id: uuid.UUID,
    payload: GenerateConversationRequest,
    current_user: CurrentUserDep,
    service: ConversationRuntimeServiceDep,
) -> AIResponse:
    """Run the runtime pipeline and return the generated response.

    Validates the request, then delegates to
    :meth:`ConversationRuntimeService.execute`. Ownership of the employee, its
    blueprint, and the conversation is enforced inside the coordinated services
    (``404``/``403``); an invalid path/body yields ``422``; provider failures
    yield ``502``/``504``. Nothing is persisted.
    """
    try:
        return service.execute(
            current_user,
            payload.employee_id,
            conversation_id,
            payload.message,
        )
    except (EmployeeError, BlueprintError, ConversationError) as exc:
        raise _to_http_exception(exc)
    except ConversationGenerationTimeoutError:
        # Subclass of ConversationGenerationError — must be caught first.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI generation timed out. Please try again.",
        )
    except ConversationGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed. Please try again later.",
        )
