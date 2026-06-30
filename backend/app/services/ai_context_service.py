"""AI context service: assemble the complete AI input for an employee.

Read-only orchestration that composes existing services — blueprint
(:class:`BlueprintService`), memory context
(:class:`MemoryContextService`), and conversation context
(:class:`ConversationContextService`) — into a single structure. Ownership is
enforced entirely by the composed services; none is re-implemented here. No AI
generation, prompts, or persistence.
"""

import uuid

from app.models.user import User
from app.schemas.ai_context import (
    AIContextResponse,
    BlueprintSection,
    ConversationSection,
    MemorySection,
)
from app.services.blueprint_service import BlueprintService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.memory_context_service import MemoryContextService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AIContextService:
    """Builds the complete AI context (blueprint + memory + conversation)."""

    def __init__(self, session) -> None:
        self.session = session
        # Reused exactly; each enforces the ownership chain it owns.
        self.blueprints = BlueprintService(session)
        self.memory = MemoryContextService(session)
        self.conversation = ConversationContextService(session)

    def build_ai_context(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> AIContextResponse:
        """Assemble the blueprint, memory, and conversation context.

        Raises ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` / ``ConversationNotFoundError`` via the
        composed services. Performs no writes.
        """
        # 1. Blueprint (employee + blueprint ownership; 404/403).
        blueprint = self.blueprints.get_blueprint(owner, employee_id)

        # 2. Memory context (reuses the employee ownership chain).
        memory_context = self.memory.build_memory_context(owner, employee_id)

        # 3. Conversation context (validates the conversation; 404).
        conversation_context = self.conversation.build_context(
            owner, employee_id, conversation_id
        )

        logger.info(
            "User %s built AI context for employee %s conversation %s "
            "(%d memories, %d messages)",
            owner.id,
            employee_id,
            conversation_id,
            memory_context.memory_count,
            conversation_context.message_count,
        )
        return AIContextResponse(
            employee_id=blueprint.employee_id,
            conversation_id=conversation_context.conversation_id,
            blueprint=BlueprintSection.model_validate(blueprint),
            memory=MemorySection.model_validate(memory_context.model_dump()),
            conversation=ConversationSection.model_validate(
                conversation_context.model_dump()
            ),
        )
