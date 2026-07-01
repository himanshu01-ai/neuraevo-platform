"""Conversation Runtime Service (Sprint 7.4).

The single runtime entry point for AI execution. It coordinates — and does
nothing else:

    AIContextEngineService.build_context()   (Sprint 7.1) -> RuntimeAIContext
    RuntimePromptBuilderService.build()       (Sprint 7.2) -> PromptPackage
    AIOrchestratorService.run()               (Sprint 7.3) -> AIResponse

It performs no AI generation, prompt building, context assembly, memory writes,
permission or tool execution, conversation updates, message saving, streaming,
or post-processing — each of those remains the responsibility of the service
that owns it. This service is stateless: it holds no session and no repository.
"""

import uuid

from app.models.user import User
from app.schemas.ai_response import AIResponse
from app.services.context import AIContextEngineService
from app.services.orchestrator import AIOrchestratorService
from app.services.prompt import RuntimePromptBuilderService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationRuntimeService:
    """Coordinates the runtime AI pipeline behind a single ``execute`` call.

    Collaborators are injected (Dependency Inversion): the Sprint 7.1 context
    engine, the Sprint 7.2 prompt builder, and the Sprint 7.3 orchestrator. All
    three are reused unchanged; this service adds only coordination.
    """

    def __init__(
        self,
        context_engine: AIContextEngineService,
        prompt_builder: RuntimePromptBuilderService,
        orchestrator: AIOrchestratorService,
    ) -> None:
        self.context_engine = context_engine
        self.prompt_builder = prompt_builder
        self.orchestrator = orchestrator

    def execute(
        self,
        owner: User,
        employee_id: uuid.UUID,
        conversation_id: uuid.UUID,
        current_user_input: str,
    ) -> AIResponse:
        """Coordinate context -> prompt -> generation and return the response.

        Exceptions raised by any coordinated service propagate unchanged. This
        method performs no writes, no persistence, and no post-processing; the
        orchestrator's :class:`AIResponse` is returned exactly as received.
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

        logger.info(
            "Conversation runtime executed for employee %s conversation %s "
            "(prompt messages=%d)",
            employee_id,
            conversation_id,
            len(package.messages),
        )
        return response
