"""AI Orchestrator (Sprint 7.3; Sprint 11.5 adds the Agent Execution Core).

Runtime orchestration only. Given a ``RuntimeAIContext`` its Sprint 7.3 ``run``:

  1. builds a ``PromptPackage`` via the Sprint 7.2 ``RuntimePromptBuilderService``,
  2. resolves the active provider via the Sprint 6 ``ConversationProviderFactory``,
  3. invokes the provider, and
  4. returns a provider-agnostic ``AIResponse``.

Sprint 11.5 adds ``execute_agent_request``, which coordinates the existing
Sprint 11.2–11.4 components (planner, tool registry, permission service, tool
execution service) into a plan-then-per-step permission-gated execution. The
orchestrator itself generates no plan, checks no permission, and executes no
tool directly — it only coordinates the injected services, in order, without
retries, exception wrapping, logging, mutation, or caching.

It performs no database or memory writes, no streaming, and no post-processing.
The reused components are not modified.
"""

from typing import List, Optional, Union

from app.schemas.agent_context import RuntimeAIContext
from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.schemas.prompt_package import PromptPackage
from app.services.permissions import (
    PermissionRequest,
    PermissionResult,
    PermissionService,
)
from app.services.planner import PlannerService
from app.services.prompt import RuntimePromptBuilderService
from app.services.providers import ConversationProviderFactory
from app.services.tools import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionService,
)
from app.services.tools.registry import ToolRegistry
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AIOrchestratorService:
    """Coordinates prompt building/generation and (Sprint 11.5) agent execution.

    Collaborators are injected (Dependency Inversion): the Sprint 7.2 prompt
    builder and the Sprint 6 provider factory power the existing ``run`` path.
    Sprint 11.5 also injects the Sprint 11.2–11.4 agent-execution collaborators
    — planner, permission service, tool registry, tool execution service — used
    only by ``execute_agent_request``. They are optional (``None`` until their
    provider seams are fulfilled), so the ``run`` path and its runtime DI chain
    are unaffected. All are reused unchanged; this service adds only coordination
    and holds no session, repository, or runtime state.
    """

    def __init__(
        self,
        prompt_builder: RuntimePromptBuilderService,
        provider_factory: ConversationProviderFactory,
        planner: Optional[PlannerService] = None,
        permissions: Optional[PermissionService] = None,
        tool_registry: Optional[ToolRegistry] = None,
        tool_execution: Optional[ToolExecutionService] = None,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.provider_factory = provider_factory
        self.planner = planner
        self.permissions = permissions
        self.tool_registry = tool_registry
        self.tool_execution = tool_execution

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

    # --- Agent Execution Core (Sprint 11.5) ------------------------------

    def execute_agent_request(
        self, user_request: str
    ) -> Union[List[ToolExecutionResult], PermissionResult]:
        """Coordinate plan -> per-step permission-gated tool execution.

        Order is exact and fixed:

          1. ``planner.create_plan(user_request)`` -> an ``ExecutionPlan``.
          2. For each ``PlanningStep`` in plan order:
             a. ``tool_registry.get_tool(step.tool_name)`` — raises ``KeyError``
                if the tool is unknown (no fallback).
             b. ``permissions.check_permission(...)`` — if the result is not
                approved, or requires user confirmation, execution STOPS
                immediately and that ``PermissionResult`` is returned directly
                (remaining steps are not executed).
             c. ``tool_execution.execute(...)`` — the result is collected.
          3. Return the collected ``ToolExecutionResult`` list, in execution
             order.

        The orchestrator only coordinates: it generates no plan, checks no
        permission, and executes no tool itself. It performs no retries, no
        exception wrapping, and no mutation — any planner/registry/permission/
        execution exception propagates unchanged, halting the remaining steps.

        The four agent-execution collaborators are optional at construction (a
        provider seam may still be unfulfilled). If any is unavailable this
        method fails fast with a clear :class:`RuntimeError` rather than an
        opaque ``AttributeError``.
        """
        if (
            self.planner is None
            or self.permissions is None
            or self.tool_registry is None
            or self.tool_execution is None
        ):
            raise RuntimeError(
                "Agent execution is unavailable because required providers "
                "have not been configured."
            )

        plan = self.planner.create_plan(user_request)

        results: List[ToolExecutionResult] = []
        for step in plan.steps:
            # a. Resolve the tool; a missing tool is a KeyError (no fallback).
            self.tool_registry.get_tool(step.tool_name)

            # b. Permission gate — halt (return the result) if not approved or
            #    if user confirmation is required.
            permission = self.permissions.check_permission(
                PermissionRequest(
                    tool_name=step.tool_name, arguments=step.arguments
                )
            )
            if (
                not permission.approved
                or permission.requires_user_confirmation
            ):
                return permission

            # c. Execute and collect, preserving order.
            result = self.tool_execution.execute(
                ToolExecutionRequest(
                    tool_name=step.tool_name, arguments=step.arguments
                )
            )
            results.append(result)

        return results

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
