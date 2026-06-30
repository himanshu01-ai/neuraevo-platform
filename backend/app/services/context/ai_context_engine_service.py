"""AI Context Engine (Sprint 7.1).

Assembles the complete runtime context required *before* any AI generation:
employee, blueprint, memories, recent conversation history, a (stub) permission
profile, language, personality, and the current user input.

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
from app.services.blueprint_service import BlueprintService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.employee_service import EmployeeService
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
    """

    def __init__(
        self,
        session,
        *,
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

        # 5. Permission profile — deny-by-default stub until the permissions
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
            permission_profile=permission_profile,
            language=employee.language,
            personality=employee.personality,
            current_user_input=current_user_input,
        )
