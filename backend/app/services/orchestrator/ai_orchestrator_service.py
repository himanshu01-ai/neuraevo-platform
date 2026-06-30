"""AI Orchestrator (Sprint 7.3).

Runtime orchestration only. Given a ``RuntimeAIContext`` it:

  1. builds a ``PromptPackage`` via the Sprint 7.2 ``RuntimePromptBuilderService``,
  2. resolves the active provider via the Sprint 6 ``ConversationProviderFactory``,
  3. invokes the provider, and
  4. returns a provider-agnostic ``AIResponse``.

It performs no database or memory writes, no tool or permission execution, no
streaming, and no post-processing of the generated text. The reused
components (prompt builder, provider factory, provider) are not modified.
"""

from app.schemas.agent_context import RuntimeAIContext
from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.schemas.prompt_package import PromptPackage
from app.services.prompt import RuntimePromptBuilderService
from app.services.providers import ConversationProviderFactory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AIOrchestratorService:
    """Coordinates prompt building and provider invocation into an AIResponse.

    Collaborators are injected (Dependency Inversion): the Sprint 7.2 prompt
    builder and the Sprint 6 provider factory. Both are reused unchanged; this
    service adds only the orchestration wiring. It holds no session and touches
    no repository.
    """

    def __init__(
        self,
        prompt_builder: RuntimePromptBuilderService,
        provider_factory: ConversationProviderFactory,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.provider_factory = provider_factory

    def run(self, context: RuntimeAIContext) -> AIResponse:
        """Build the prompt, invoke the active provider, and wrap the reply.

        Provider failures (``ConversationGenerationError`` /
        ``ConversationGenerationTimeoutError``) propagate unchanged. Performs no
        writes and no post-processing of the returned text.
        """
        # 1. Build the structured prompt (Sprint 7.2; pure transform).
        package = self.prompt_builder.build(context)

        # 2. Resolve the active provider (Sprint 6E factory).
        provider = self.provider_factory.get_provider()

        # 3. Adapt the structured package to the provider's string interface
        #    (``ConversationProvider.generate_reply(prompt: str)`` is a Sprint 6
        #    contract that must not be modified), then invoke it.
        prompt = self._render_prompt(package)
        content = provider.generate_reply(prompt)

        logger.info(
            "Orchestrated AI response for employee %s conversation %s "
            "(provider=%s, %d prompt messages)",
            package.metadata.employee_id,
            package.metadata.conversation_id,
            provider.name,
            len(package.messages),
        )

        # 4. Wrap in a provider-agnostic DTO. ``content`` is returned verbatim.
        return AIResponse(
            content=content,
            metadata=AIResponseMetadata(
                provider=provider.name,
                language=package.language,
                employee_id=package.metadata.employee_id,
                conversation_id=package.metadata.conversation_id,
                prompt_message_count=len(package.messages),
            ),
        )

    @staticmethod
    def _render_prompt(package: PromptPackage) -> str:
        """Flatten the structured package into the single prompt string the
        Sprint 6 ``ConversationProvider`` expects.

        Mechanical serialization only (no prompt engineering): the assembled
        system block followed by the message transcript. This is purely an
        interface adapter, because the provider contract
        (``generate_reply(prompt: str)``) is immutable in this sprint.
        """
        lines = [package.system_prompt, ""]
        for message in package.messages:
            lines.append(f"{message.role}: {message.content}")
        return "\n".join(lines)
