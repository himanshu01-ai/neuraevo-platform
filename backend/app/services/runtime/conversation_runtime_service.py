"""Conversation Runtime Service (Sprint 7.4, integrated in Sprint 8.2).

The single runtime entry point for AI execution. It coordinates — and does
nothing else:

    AIContextEngineService.build_context()    (Sprint 7.1) -> RuntimeAIContext
    RuntimePromptBuilderService.build()        (Sprint 7.2) -> PromptPackage
    AIOrchestratorService.run()                (Sprint 7.3) -> AIResponse
    MemoryPersistenceService.persist()         (Sprint 8.1) -> persists the turn

It still performs none of that work itself — AI generation, prompt building,
context assembly, and the message writes each remain the responsibility of the
service that owns them; this service only coordinates. As of Sprint 8.2 it
persists the completed turn (via :class:`MemoryPersistenceService`) immediately
after generation and before returning. It holds no session and no repository;
the persistence service owns commits/rollback.
"""

import uuid

from app.models.user import User
from app.schemas.ai_response import AIResponse
from app.services.context import AIContextEngineService
from app.services.memory import MemoryPersistenceService
from app.services.orchestrator import AIOrchestratorService
from app.services.prompt import RuntimePromptBuilderService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationRuntimeService:
    """Coordinates the runtime AI pipeline behind a single ``execute`` call.

    Collaborators are injected (Dependency Inversion): the Sprint 7.1 context
    engine, the Sprint 7.2 prompt builder, the Sprint 7.3 orchestrator, and the
    Sprint 8.1 memory persistence service. All are reused unchanged; this
    service adds only coordination.
    """

    def __init__(
        self,
        context_engine: AIContextEngineService,
        prompt_builder: RuntimePromptBuilderService,
        orchestrator: AIOrchestratorService,
        memory_persistence: MemoryPersistenceService,
    ) -> None:
        self.context_engine = context_engine
        self.prompt_builder = prompt_builder
        self.orchestrator = orchestrator
        self.memory_persistence = memory_persistence

    def execute(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        current_user_input: str,
    ) -> AIResponse:
        """Coordinate context -> prompt -> generation -> persistence.

        Assembles context, builds the prompt, generates the response, then
        persists the completed turn (Sprint 8.2) via
        :class:`MemoryPersistenceService` before returning the unchanged
        :class:`AIResponse`. Exceptions raised by any coordinated service —
        including persistence — propagate unchanged; persistence runs only after
        a successful generation and is never wrapped or swallowed here.
        """
        # 1. Assemble the runtime context (Sprint 7.1; ownership enforced there).
        context = self.context_engine.build_context(
            owner, employee_id, conversation_id, current_user_input
        )

        # 2. Build the prompt package (Sprint 7.2; pure transform). The Sprint
        #    7.3 orchestrator re-derives this from the context internally (its
        #    contract takes the context and must not be modified); this explicit
        #    step keeps the coordination visible and provides prompt telemetry.
        package = self.prompt_builder.build(context)

        # 3. Generate the response (Sprint 7.3). Returned unchanged.
        response = self.orchestrator.run(context)

        # 4. Persist the completed turn (Sprint 8.2): the user input and the
        #    assistant response are written via MemoryPersistenceService, which
        #    owns the transaction (commit/rollback). This runs only after a
        #    successful generation and before returning. Persistence exceptions
        #    are not caught here — they propagate exactly as thrown.
        self.memory_persistence.persist(
            owner,
            employee_id,
            conversation_id,
            current_user_input,
            response,
        )

        logger.info(
            "Conversation runtime executed for employee %s conversation %s "
            "(prompt messages=%d)",
            employee_id,
            conversation_id,
            len(package.messages),
        )
        return response
