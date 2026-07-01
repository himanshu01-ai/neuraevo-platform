"""AI Context Engine (Sprint 7.1; Sprint 9.2 adds retrieved-history).

Assembles the complete runtime context required *before* any AI generation:
employee, blueprint, memories, recent conversation history, retrieved message
history, a (stub) permission profile, language, personality, and the current
user input.

Read-only orchestration that composes existing domain services for loading and
ownership validation. It does not duplicate any ownership logic, and it performs
no provider imports, no AI/Claude/OpenAI calls, no prompt building, and no
database writes. The next sprint(s) — prompt building, tool calling, permission
execution, memory writing — are intentionally out of scope here.
"""

import uuid
from typing import Optional

from app.models.user import User
from app.schemas.agent_context import PermissionProfile, RuntimeAIContext
from app.schemas.blueprint import BlueprintResponse
from app.schemas.employee import EmployeeResponse
from app.schemas.message import MessageResponse
from app.services.blueprint_service import BlueprintService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.employee_service import EmployeeService
from app.services.memory import MemoryRetrievalService
from app.services.memory_context_service import MemoryContextService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AIContextEngineService:
    """Assembles the runtime ``RuntimeAIContext`` from existing domain services.

    Collaborators are injected (Dependency Inversion): each is provided
    explicitly for testing, or defaults to a session-bound instance so the
    FastAPI provider stays a one-liner. Ownership is enforced entirely by these
    reused services — each owns the chain it validates — so none is
    re-implemented here. The service performs no writes and knows nothing about
    prompts or providers.

    ``memory_retrieval`` (Sprint 9.2) is the Sprint 9.1
    :class:`MemoryRetrievalService`. Unlike the collaborators above, it is
    required (not optional/session-defaulted): its own constructor takes a
    repository instance rather than a session, so building a default here
    would require this engine to import and construct a repository directly —
    which would violate the composition-root boundary. Following the same
    precedent as ``ConversationRuntimeService`` receiving
    ``MemoryPersistenceService`` (Sprint 8.2), it is wired exclusively by
    ``core/dependencies.py`` via the existing ``get_memory_retrieval_service``
    provider and always injected. It performs no ownership validation of its
    own — it is only ever called here after the conversation's ownership has
    already been validated.
    """

    def __init__(
        self,
        session,
        *,
        memory_retrieval: MemoryRetrievalService,
        employees: Optional[EmployeeService] = None,
        blueprints: Optional[BlueprintService] = None,
        memory: Optional[MemoryContextService] = None,
        conversation: Optional[ConversationContextService] = None,
    ) -> None:
        self.session = session
        self.employees = employees or EmployeeService(session)
        self.blueprints = blueprints or BlueprintService(session)
        self.memory = memory or MemoryContextService(session)
        self.conversation = conversation or ConversationContextService(session)
        self.memory_retrieval = memory_retrieval

    def build_context(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        current_user_input: str,
    ) -> RuntimeAIContext:
        """Assemble the full runtime context for an employee conversation.

        Ownership is validated by the composed services, which raise
        ``EmployeeNotFoundError`` / ``EmployeeAccessDeniedError`` /
        ``BlueprintNotFoundError`` / ``ConversationNotFoundError`` as
        appropriate. Performs no writes.
        """
        # 1. Employee (User -> Employee ownership; 404/403). Also the source of
        #    language and personality.
        employee = self.employees.get_employee(owner, employee_id)

        # 2. Blueprint (ownership inherited from the employee; 404/403).
        blueprint = self.blueprints.get_blueprint(owner, employee_id)

        # 3. Memory context (reuses the employee ownership chain).
        memory_context = self.memory.build_memory_context(owner, employee_id)

        # 4. Recent conversation history (validates the conversation; 404). The
        #    recency window is owned by the conversation context service.
        conversation_context = self.conversation.build_context(
            owner, employee_id, conversation_id
        )

        # 5. Retrieved message history (Sprint 9.2). Conversation ownership was
        #    already validated in step 4 above, so MemoryRetrievalService is
        #    called with no further authorization checks of its own.
        retrieved_messages = self.memory_retrieval.retrieve(
            owner, employee_id, conversation_id
        )

        # 6. Permission profile — deny-by-default stub until the permissions
        #    sprint. Assembled here so the runtime context shape is stable.
        permission_profile = PermissionProfile()

        logger.info(
            "User %s assembled runtime AI context for employee %s "
            "conversation %s (%d memories, %d messages)",
            owner.id,
            employee_id,
            conversation_id,
            memory_context.memory_count,
            conversation_context.message_count,
        )

        return RuntimeAIContext(
            employee=EmployeeResponse.model_validate(employee),
            blueprint=BlueprintResponse.model_validate(blueprint),
            memories=memory_context,
            recent_conversation=conversation_context,
            retrieved_history=[
                MessageResponse.model_validate(message)
                for message in retrieved_messages
            ],
            permission_profile=permission_profile,
            language=employee.language,
            personality=employee.personality,
            current_user_input=current_user_input,
        )
