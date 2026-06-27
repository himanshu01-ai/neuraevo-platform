"""Conversation generation service.

Orchestrates an assistant reply: resolves blueprint ownership, builds context
(Sprint 5C), calls a :class:`ConversationProvider`, then (Sprint 5E) persists
the reply as an assistant :class:`Message` and returns it. Generation remains
read-only until a reply is produced; only after a successful generation is the
message created and committed (atomically). The provider is injected (DI).
"""

import uuid

from app.models.message import Message
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate
from app.services.blueprint_service import BlueprintService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.providers.conversation_provider import ConversationProvider
from app.utils.constants import MessageRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationGenerationService:
    """Generates an assistant reply and persists it as a message.

    Ownership is enforced by reusing :meth:`BlueprintService.get_blueprint`
    (employee + blueprint) and :class:`ConversationContextService`
    (conversation). Message persistence reuses the Sprint 5B
    :class:`MessageRepository`; this service owns the transaction.
    """

    def __init__(self, session, provider: ConversationProvider) -> None:
        self.session = session
        self.blueprints = BlueprintService(session)
        self.context = ConversationContextService(session)
        # Reuse Sprint 5B message persistence (no second repository).
        self.messages = MessageRepository(session)
        self.provider = provider

    def generate_reply(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Message:
        """Generate the next assistant reply and store it as a message.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` / ``ConversationNotFoundError`` via the
        reused ownership chains, and the provider's
        ``ConversationGenerationError`` / ``...TimeoutError`` on generation
        failure (in which case nothing is written). On success, exactly one
        assistant message is created and committed atomically; any persistence
        failure rolls back, leaving no partial write.
        """
        # 1. Resolve blueprint ownership (employee + blueprint; 404/403).
        blueprint = self.blueprints.get_blueprint(owner, employee_id)

        # 2. Build context (validates conversation ownership; 404).
        context = self.context.build_context(
            owner, employee_id, conversation_id
        )

        # 3. Generate the reply (read-only; raises 502/504 -> nothing written).
        reply = self.provider.generate_reply(blueprint, context)

        # 4. Persist the assistant message, then commit. Commit happens only
        #    after a successful generation; any failure rolls back so there is
        #    no partial write.
        try:
            message = self.messages.create_message(
                context.conversation_id,
                MessageCreate(role=MessageRole.ASSISTANT, content=reply),
            )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(message)

        logger.info(
            "User %s generated and stored assistant message %s in "
            "conversation %s (%d prior messages, provider=%s)",
            owner.id,
            message.id,
            context.conversation_id,
            context.message_count,
            self.provider.name,
        )
        return message
