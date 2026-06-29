"""Conversation generation service.

Orchestrates an assistant reply. As of Sprint 6D it no longer assembles
blueprint, memory, or conversation data itself: it builds the unified AI
context (:class:`AIContextService`, Sprint 6C), renders it into a prompt
(:class:`PromptBuilderService`), hands that prompt to a
:class:`ConversationProvider`, then (Sprint 5E) persists the reply as an
assistant :class:`Message` and returns it. Generation remains read-only until a
reply is produced; only after a successful generation is the message created
and committed (atomically). This service orchestrates only — it knows nothing
about how prompts are constructed.
"""

import uuid

from app.models.message import Message
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.schemas.message import MessageCreate
from app.services.ai_context_service import AIContextService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.providers.conversation_provider import ConversationProvider
from app.utils.constants import MessageRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationGenerationService:
    """Generates an assistant reply and persists it as a message.

    Ownership is enforced entirely by the reused :class:`AIContextService`
    (employee + blueprint + conversation chains); none is re-implemented here.
    Message persistence reuses the Sprint 5B :class:`MessageRepository`; this
    service owns the transaction.
    """

    def __init__(
        self,
        session,
        provider: ConversationProvider,
        ai_context: AIContextService,
        prompt_builder: PromptBuilderService,
    ) -> None:
        self.session = session
        self.ai_context = ai_context
        self.prompt_builder = prompt_builder
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
        # 1. Build the unified AI context (blueprint + memory + conversation).
        #    All ownership validation (employee/blueprint 404/403, conversation
        #    404) is enforced inside the reused service.
        ai_context = self.ai_context.build_ai_context(
            owner, employee_id, conversation_id
        )

        # 2. Render the context into a prompt (pure deterministic transform).
        prompt = self.prompt_builder.build_prompt(ai_context)

        # 3. Generate the reply. The provider receives only the prompt string
        #    (read-only; raises 502/504 -> nothing written).
        reply = self.provider.generate_reply(prompt)

        # 4. Persist the assistant message, then commit. Commit happens only
        #    after a successful generation; any failure rolls back so there is
        #    no partial write.
        try:
            message = self.messages.create_message(
                ai_context.conversation_id,
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
            ai_context.conversation_id,
            ai_context.conversation.message_count,
            self.provider.name,
        )
        return message
