"""Conversation generation service (preview).

Orchestrates a read-only conversation reply: resolves blueprint ownership,
builds context (Sprint 5C), and calls a :class:`ConversationProvider`. Sprint
5D performs no persistence — it never creates messages, mutates conversations,
or commits. The provider is injected (DI).
"""

import uuid

from app.models.user import User
from app.schemas.conversation_generation import ConversationGenerationResponse
from app.services.blueprint_service import BlueprintService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.providers.conversation_provider import ConversationProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationGenerationService:
    """Coordinates non-persisting conversation reply generation.

    Read-only: never commits. Ownership is enforced by reusing
    :meth:`BlueprintService.get_blueprint` (employee + blueprint) and
    :class:`ConversationContextService` (conversation), which raise the domain
    errors the API translates to 404/403.
    """

    def __init__(self, session, provider: ConversationProvider) -> None:
        self.session = session
        self.blueprints = BlueprintService(session)
        self.context = ConversationContextService(session)
        self.provider = provider

    def generate_reply(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> ConversationGenerationResponse:
        """Generate the next assistant reply for a conversation (no writes).

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` / ``ConversationNotFoundError`` via the
        reused ownership chains, and the provider's
        ``ConversationGenerationError`` / ``...TimeoutError`` on generation
        failure. Performs no persistence.
        """
        # 1. Resolve blueprint ownership (employee + blueprint; 404/403).
        blueprint = self.blueprints.get_blueprint(owner, employee_id)

        # 2. Build context (validates conversation ownership; 404).
        context = self.context.build_context(
            owner, employee_id, conversation_id
        )

        # 3. Call provider (read-only; raises 502/504 on failure).
        reply = self.provider.generate_reply(blueprint, context)

        logger.info(
            "User %s generated a conversation reply for conversation %s "
            "(%d context messages, provider=%s)",
            owner.id,
            conversation_id,
            context.message_count,
            self.provider.name,
        )
        return ConversationGenerationResponse(reply=reply)
