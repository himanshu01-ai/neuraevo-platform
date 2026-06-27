"""FastAPI dependency providers.

Wires the database session into the service layer and exposes
``get_current_user`` for protecting routes with JWT bearer authentication.
"""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.employee_builder.blueprint import BlueprintGenerationProvider
from app.employee_builder.providers import ClaudeBlueprintProvider
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.blueprint_apply_service import BlueprintApplyService
from app.services.blueprint_generation_service import BlueprintGenerationService
from app.services.blueprint_restore_service import BlueprintRestoreService
from app.services.blueprint_service import BlueprintService
from app.services.blueprint_version_service import BlueprintVersionService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.employee_service import EmployeeService
from app.services.interview_answer_service import InterviewAnswerService
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_session_question_service import (
    InterviewSessionQuestionService,
)
from app.services.interview_session_service import InterviewSessionService
from app.services.memory_service import MemoryService

# ``auto_error=True`` => a missing/blank Authorization header is rejected by the
# scheme (401) before our handler runs; we also raise 401 for malformed/expired
# tokens below, so unauthenticated requests consistently receive 401.
_bearer_scheme = HTTPBearer(auto_error=True)

SessionDep = Annotated[Session, Depends(get_db)]


def get_auth_service(session: SessionDep) -> AuthService:
    """Provide an :class:`AuthService` bound to the request-scoped session."""
    return AuthService(session)


def get_employee_service(session: SessionDep) -> EmployeeService:
    """Provide an :class:`EmployeeService` bound to the request-scoped session."""
    return EmployeeService(session)


def get_memory_service(session: SessionDep) -> MemoryService:
    """Provide a :class:`MemoryService` bound to the request-scoped session."""
    return MemoryService(session)


def get_blueprint_service(session: SessionDep) -> BlueprintService:
    """Provide a :class:`BlueprintService` bound to the request-scoped session."""
    return BlueprintService(session)


def get_blueprint_generation_provider() -> BlueprintGenerationProvider:
    """Provide the default (Claude) blueprint generation provider.

    Reads the API key/model from settings; swapping providers is a one-line
    change here with no impact on services or routers.
    """
    return ClaudeBlueprintProvider(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        timeout=settings.ANTHROPIC_TIMEOUT_SECONDS,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
    )


BlueprintGenerationProviderDep = Annotated[
    BlueprintGenerationProvider, Depends(get_blueprint_generation_provider)
]


def get_blueprint_generation_service(
    session: SessionDep,
    provider: BlueprintGenerationProviderDep,
) -> BlueprintGenerationService:
    """Provide a :class:`BlueprintGenerationService` bound to the session."""
    return BlueprintGenerationService(session, provider)


def get_blueprint_apply_service(
    session: SessionDep,
    provider: BlueprintGenerationProviderDep,
) -> BlueprintApplyService:
    """Provide a :class:`BlueprintApplyService` bound to the session."""
    return BlueprintApplyService(session, provider)


def get_blueprint_version_service(
    session: SessionDep,
) -> BlueprintVersionService:
    """Provide a :class:`BlueprintVersionService` bound to the session."""
    return BlueprintVersionService(session)


def get_blueprint_restore_service(
    session: SessionDep,
) -> BlueprintRestoreService:
    """Provide a :class:`BlueprintRestoreService` bound to the session."""
    return BlueprintRestoreService(session)


def get_conversation_service(session: SessionDep) -> ConversationService:
    """Provide a :class:`ConversationService` bound to the session."""
    return ConversationService(session)


def get_message_service(session: SessionDep) -> MessageService:
    """Provide a :class:`MessageService` bound to the session."""
    return MessageService(session)


def get_conversation_context_service(
    session: SessionDep,
) -> ConversationContextService:
    """Provide a :class:`ConversationContextService` bound to the session."""
    return ConversationContextService(session)


def get_interview_question_service(
    session: SessionDep,
) -> InterviewQuestionService:
    """Provide an :class:`InterviewQuestionService` bound to the session."""
    return InterviewQuestionService(session)


def get_interview_answer_service(
    session: SessionDep,
) -> InterviewAnswerService:
    """Provide an :class:`InterviewAnswerService` bound to the session."""
    return InterviewAnswerService(session)


def get_interview_session_service(
    session: SessionDep,
) -> InterviewSessionService:
    """Provide an :class:`InterviewSessionService` bound to the session."""
    return InterviewSessionService(session)


def get_interview_session_question_service(
    session: SessionDep,
) -> InterviewSessionQuestionService:
    """Provide an :class:`InterviewSessionQuestionService` bound to the session."""
    return InterviewSessionQuestionService(session)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the authenticated user from a Bearer *access* token.

    Raises ``401 Unauthorized`` if the token is invalid, expired, of the wrong
    type, or does not map to an active user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise credentials_exception

    if claims.get("type") != "access":
        raise credentials_exception

    subject = claims.get("sub")
    if not subject:
        raise credentials_exception
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exception

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
BlueprintServiceDep = Annotated[BlueprintService, Depends(get_blueprint_service)]
BlueprintGenerationServiceDep = Annotated[
    BlueprintGenerationService, Depends(get_blueprint_generation_service)
]
BlueprintApplyServiceDep = Annotated[
    BlueprintApplyService, Depends(get_blueprint_apply_service)
]
BlueprintVersionServiceDep = Annotated[
    BlueprintVersionService, Depends(get_blueprint_version_service)
]
BlueprintRestoreServiceDep = Annotated[
    BlueprintRestoreService, Depends(get_blueprint_restore_service)
]
ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
ConversationContextServiceDep = Annotated[
    ConversationContextService, Depends(get_conversation_context_service)
]
InterviewQuestionServiceDep = Annotated[
    InterviewQuestionService, Depends(get_interview_question_service)
]
InterviewAnswerServiceDep = Annotated[
    InterviewAnswerService, Depends(get_interview_answer_service)
]
InterviewSessionServiceDep = Annotated[
    InterviewSessionService, Depends(get_interview_session_service)
]
InterviewSessionQuestionServiceDep = Annotated[
    InterviewSessionQuestionService,
    Depends(get_interview_session_question_service),
]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
