"""FastAPI dependency providers.

Wires the database session into the service layer and exposes
``get_current_user`` for protecting routes with JWT bearer authentication.
"""

import uuid
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.employee_builder.blueprint import BlueprintGenerationProvider
from app.employee_builder.providers import ClaudeBlueprintProvider
from app.models.user import User
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_context_service import AIContextService
from app.services.auth_service import AuthService
from app.services.context import AIContextEngineService
from app.services.blueprint_apply_service import BlueprintApplyService
from app.services.blueprint_generation_service import BlueprintGenerationService
from app.services.blueprint_restore_service import BlueprintRestoreService
from app.services.blueprint_service import BlueprintService
from app.services.blueprint_version_service import BlueprintVersionService
from app.services.conversation_context_service import (
    ConversationContextService,
)
from app.services.conversation_generation_service import (
    ConversationGenerationService,
)
from app.services.conversation_service import ConversationService
from app.services.memory_context_service import MemoryContextService
from app.services.message_service import MessageService
from app.services.prompt_builder_service import PromptBuilderService
from app.services.prompt import RuntimePromptBuilderService
from app.services.orchestrator import AIOrchestratorService
from app.services.runtime import ConversationRuntimeService
from app.services.runtime.execution_runtime import ExecutionRuntime
from app.services.runtime.task_dispatcher import TaskDispatcher
from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.capability_dispatcher import CapabilityDispatcher
from app.services.runtime.capability_executor import CapabilityExecutor
from app.services.runtime.execution_progress_runtime import (
    ExecutionProgressRuntime,
)
from app.services.runtime.execution_controller import ExecutionController
from app.services.runtime.execution_event_manager import ExecutionEventManager
from app.services.runtime.execution_lifecycle_manager import (
    ExecutionLifecycleManager,
)
from app.services.runtime.runtime_execution_state_manager import (
    RuntimeExecutionStateManager,
)
from app.services.runtime.runtime_execution_monitor import (
    RuntimeExecutionMonitor,
)
from app.services.runtime.runtime_pause_resume_manager import (
    RuntimePauseResumeManager,
)
from app.services.runtime.runtime_recovery_coordinator import (
    RuntimeRecoveryCoordinator,
)
from app.services.runtime.runtime_resource_coordinator import (
    RuntimeResourceCoordinator,
)
from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import (
    CapabilityDefinition,
)
from app.services.runtime.capability_resolver import CapabilityResolver
from app.services.runtime.capability_metadata import CapabilityMetadataManager
from app.services.runtime.capability_discovery import CapabilityDiscoveryManager
from app.services.runtime.capability_validation import CapabilityValidationManager
from app.services.runtime.browser_capability import (
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    BrowserCapability,
    PlaywrightBrowserDriver,
)
from app.services.runtime.browser_dom import BrowserDOM
from app.services.runtime.browser_interaction import BrowserInteraction
from app.services.runtime.browser_workspace import BrowserWorkspace
from app.services.runtime.python_capability import PythonCapability
from app.services.runtime.filesystem_capability import FileSystemCapability
from app.services.runtime.email_capability import EmailCapability
from app.services.runtime.calendar_capability import CalendarCapability
from app.services.runtime.github_capability import GitHubCapability
from app.services.runtime.capability_router import CapabilityRouter
from app.services.runtime.artifact_coordinator import ArtifactCoordinator
from app.services.runtime.workflow_coordinator import WorkflowCoordinator
from app.services.ai_employee import AIEmployee
from app.services.ai_employee import (
    ApprovalManager,
    AutoApprovalPolicy,
    BasicRecoveryManager,
    InMemoryNotificationManager,
    InMemoryPersistenceManager,
    NotificationManager,
    PersistenceManager,
    ProgressTracker,
    RecoveryManager as WorkflowRecoveryManager,
    WorkflowLifecycleManager,
)
# Sprint 16.3 Human Approval Engine — imported as a namespaced module so its
# ``ApprovalManager``/``AutoApprovalPolicy`` (distinct from the frozen Sprint 16.2
# classes of the same name imported above) never collide in the composition root.
import app.services.ai_employee.approval as approval_engine
# Sprint 16.4 Notification Engine — imported as a namespaced module so its
# ``NotificationManager`` (distinct from the frozen Sprint 16.2 class of the same
# name imported above) never collides in the composition root.
import app.services.ai_employee.notification as notification_engine
# Sprint 16.5 Persistence Layer — imported as a namespaced module so its
# ``PersistenceManager`` (distinct from the frozen Sprint 16.2 class of the same
# name imported above) never collides in the composition root.
import app.services.ai_employee.persistence as persistence_engine
# Sprint 16.6 Memory Orchestrator — imported as a namespaced module (kept distinct
# from the frozen ``app.services.memory`` semantic-memory services) so the
# composition root reads unambiguously.
import app.services.ai_employee.memory as memory_engine
# Sprint 16.7 Scheduling Platform — imported as a namespaced module so its
# ``ExecutionScheduler`` (distinct from the frozen Sprint 13.11 planning
# ``ExecutionScheduler`` imported above) never collides in the composition root.
import app.services.ai_employee.scheduler as scheduler_engine
# Sprint 16.8 Recovery engine — imported as a namespaced module so its
# ``RecoveryManager`` (distinct from the frozen Sprint 13.13 planning and Sprint
# 16.2 workflow ``RecoveryManager`` imported above) never collides in the
# composition root.
import app.services.ai_employee.recovery as recovery_engine
# Sprint 16.9 Agent Coordination Platform — imported as a namespaced module so its
# coordinator/registry/resolver/policy names stay isolated in the composition root.
import app.services.ai_employee.coordination as coordination_platform
# Sprint 16.10 AI Employee Service Layer — imported as a namespaced module so its
# service/session/validator/health names stay isolated in the composition root.
import app.services.ai_employee.service as ai_employee_service
# Sprint 16.11 Enterprise Operations Layer — imported as a namespaced module so its
# authorization/audit/observability/deployment names stay isolated in the root.
import app.services.ai_employee.operations as enterprise_operations
# Sprint 16.12 Experience Intelligence Platform — imported as a namespaced module so
# its feedback/analyzer/evaluator/reporter names stay isolated in the root.
import app.services.ai_employee.experience as experience_intelligence
# Sprint 16.13 Production Validation Platform — imported as a namespaced module so its
# system/integration/security/compatibility validator names stay isolated in the root.
import app.services.ai_employee.validation as production_validation
from app.services.memory import MemoryPersistenceService, MemoryRetrievalService
from app.services.embeddings import EmbeddingProvider, EmbeddingService
from app.services.vector_store import (
    QdrantProvider,
    VectorStoreProvider,
    VectorStoreService,
)
from app.services.tools import ToolExecutionService, ToolProvider
from app.services.tools.registry import ToolRegistry
from app.services.permissions import PermissionProvider, PermissionService
from app.services.planner import PlannerProvider, PlannerService
from app.services.planning import (
    HeuristicPlanningProvider,
    PlanningEngine,
    PlanningExplanationBuilder,
    PlanningProvider,
    PlanValidator,
)
from app.services.planning.plan_analyzer import PlanAnalyzer
from app.services.planning.execution_preparation_engine import (
    ExecutionPreparationEngine,
)
from app.services.planning.decision_engine import DecisionEngine
from app.services.planning.execution_intent_engine import ExecutionIntentEngine
from app.services.planning.execution_orchestrator import ExecutionOrchestrator
from app.services.planning.execution_coordinator import ExecutionCoordinator
from app.services.planning.task_lifecycle_engine import TaskLifecycleEngine
from app.services.planning.execution_state_manager import ExecutionStateManager
from app.services.planning.execution_dependency_graph import (
    ExecutionDependencyGraphBuilder,
)
from app.services.planning.execution_scheduler import ExecutionScheduler
from app.services.planning.execution_monitor import ExecutionMonitor
from app.services.planning.recovery_manager import RecoveryManager
from app.services.planning.human_approval_manager import HumanApprovalManager
from app.services.interaction import (
    InteractionProvider,
    InteractionService,
)
from app.services.providers import ConversationProviderFactory
from app.services.employee_service import EmployeeService
from app.services.interview_answer_service import InterviewAnswerService
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_session_question_service import (
    InterviewSessionQuestionService,
)
from app.services.interview_session_service import InterviewSessionService
from app.services.memory_service import MemoryService

# ``auto_error=True`` => a missing/blank Authorization header is rejected by the
# scheme (401) before our handler runs; we also raise 401 for malformed/expired
# tokens below, so unauthenticated requests consistently receive 401.
_bearer_scheme = HTTPBearer(auto_error=True)

SessionDep = Annotated[Session, Depends(get_db)]


def get_auth_service(session: SessionDep) -> AuthService:
    """Provide an :class:`AuthService` bound to the request-scoped session."""
    return AuthService(session)


def get_employee_service(session: SessionDep) -> EmployeeService:
    """Provide an :class:`EmployeeService` bound to the request-scoped session."""
    return EmployeeService(session)


def get_memory_service(session: SessionDep) -> MemoryService:
    """Provide a :class:`MemoryService` bound to the request-scoped session."""
    return MemoryService(session)


def get_blueprint_service(session: SessionDep) -> BlueprintService:
    """Provide a :class:`BlueprintService` bound to the request-scoped session."""
    return BlueprintService(session)


def get_blueprint_generation_provider() -> BlueprintGenerationProvider:
    """Provide the default (Claude) blueprint generation provider.

    Reads the API key/model from settings; swapping providers is a one-line
    change here with no impact on services or routers.
    """
    return ClaudeBlueprintProvider(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        timeout=settings.ANTHROPIC_TIMEOUT_SECONDS,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
    )


BlueprintGenerationProviderDep = Annotated[
    BlueprintGenerationProvider, Depends(get_blueprint_generation_provider)
]


def get_blueprint_generation_service(
    session: SessionDep,
    provider: BlueprintGenerationProviderDep,
) -> BlueprintGenerationService:
    """Provide a :class:`BlueprintGenerationService` bound to the session."""
    return BlueprintGenerationService(session, provider)


def get_blueprint_apply_service(
    session: SessionDep,
    provider: BlueprintGenerationProviderDep,
) -> BlueprintApplyService:
    """Provide a :class:`BlueprintApplyService` bound to the session."""
    return BlueprintApplyService(session, provider)


def get_blueprint_version_service(
    session: SessionDep,
) -> BlueprintVersionService:
    """Provide a :class:`BlueprintVersionService` bound to the session."""
    return BlueprintVersionService(session)


def get_blueprint_restore_service(
    session: SessionDep,
) -> BlueprintRestoreService:
    """Provide a :class:`BlueprintRestoreService` bound to the session."""
    return BlueprintRestoreService(session)


def get_conversation_service(session: SessionDep) -> ConversationService:
    """Provide a :class:`ConversationService` bound to the session."""
    return ConversationService(session)


def get_message_service(session: SessionDep) -> MessageService:
    """Provide a :class:`MessageService` bound to the session."""
    return MessageService(session)


def get_memory_context_service(
    session: SessionDep,
) -> MemoryContextService:
    """Provide a :class:`MemoryContextService` bound to the session."""
    return MemoryContextService(session)


def get_embedding_provider() -> EmbeddingProvider:
    """Provide the active embedding provider (Sprint 10.1).

    Sprint 10.1 ships only the abstraction — no concrete embedding provider
    exists yet — so this composition-root seam is intentionally unfulfilled and
    raises. A later sprint registers a real provider here (the one place
    providers are constructed), with no change required in
    :class:`EmbeddingService` or its consumers.
    """
    raise NotImplementedError(
        "No embedding provider is implemented yet (Sprint 10.1 ships only the "
        "abstraction); a concrete provider is wired here in a later sprint."
    )


EmbeddingProviderDep = Annotated[
    EmbeddingProvider, Depends(get_embedding_provider)
]


def get_embedding_service(
    provider: EmbeddingProviderDep,
) -> EmbeddingService:
    """Provide an :class:`EmbeddingService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — it is the Sprint 10.1 abstraction only.
    """
    return EmbeddingService(provider)


EmbeddingServiceDep = Annotated[
    EmbeddingService, Depends(get_embedding_service)
]


def get_vector_store_provider() -> VectorStoreProvider:
    """Provide the active vector-store provider (Qdrant) from settings.

    Connection settings are read here in the composition root and handed to the
    provider; the Qdrant client itself is built lazily on first use, so this
    provider is constructed without importing the SDK or contacting a server.
    Swapping vector stores is a change confined to this one line.
    """
    return QdrantProvider(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )


VectorStoreProviderDep = Annotated[
    VectorStoreProvider, Depends(get_vector_store_provider)
]


def get_vector_store_service(
    provider: VectorStoreProviderDep,
) -> VectorStoreService:
    """Provide a :class:`VectorStoreService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — Sprint 10.2 infrastructure only.
    """
    return VectorStoreService(provider)


VectorStoreServiceDep = Annotated[
    VectorStoreService, Depends(get_vector_store_service)
]


def get_optional_embedding_service() -> Optional[EmbeddingService]:
    """Provide an :class:`EmbeddingService` if available, else ``None``.

    Sprint 10.1's ``get_embedding_provider`` seam is intentionally unfulfilled
    (no concrete provider yet). Rather than let that break the runtime pipeline
    at dependency-resolution time, this composition-root assembler tolerates the
    gap: when no provider is available it returns ``None``. Consumers degrade
    gracefully — memory persistence skips indexing (Sprint 10.3) and semantic
    retrieval is simply unavailable (Sprint 10.4) — while their session-bound,
    non-embedding paths keep working. Once a concrete provider is registered in
    a later sprint, this returns a real :class:`EmbeddingService` and both
    activate with no further changes.
    """
    try:
        provider = get_embedding_provider()
    except NotImplementedError:
        return None
    return EmbeddingService(provider)


OptionalEmbeddingServiceDep = Annotated[
    Optional[EmbeddingService], Depends(get_optional_embedding_service)
]


def get_memory_persistence_service(
    session: SessionDep,
    embeddings: OptionalEmbeddingServiceDep,
    vector_store: VectorStoreServiceDep,
) -> MemoryPersistenceService:
    """Provide a :class:`MemoryPersistenceService` bound to the session.

    The reused Sprint 5B :class:`MessageRepository` is wired here in the
    composition root and injected into the service, so the service never
    instantiates a repository itself (Sprint 8.1). Sprint 10.3 also injects the
    Sprint 10.1 :class:`EmbeddingService` (or ``None`` until its provider is
    implemented) and the Sprint 10.2 :class:`VectorStoreService`, so the service
    can index a persisted memory after the authoritative DB commit — it never
    instantiates a service or provider itself.
    """
    return MemoryPersistenceService(
        session, MessageRepository(session), embeddings, vector_store
    )


MemoryPersistenceServiceDep = Annotated[
    MemoryPersistenceService, Depends(get_memory_persistence_service)
]


def get_memory_retrieval_service(
    session: SessionDep,
    embeddings: OptionalEmbeddingServiceDep,
    vector_store: VectorStoreServiceDep,
) -> MemoryRetrievalService:
    """Provide a :class:`MemoryRetrievalService` bound to the session.

    The reused Sprint 5B :class:`MessageRepository` is wired here in the
    composition root and injected into the service, so the service never
    instantiates a repository itself (Sprint 9.1). Sprint 10.4 also injects the
    Sprint 10.1 :class:`EmbeddingService` (or ``None`` until its provider is
    implemented) and the Sprint 10.2 :class:`VectorStoreService`, so the service
    can perform semantic retrieval — it never instantiates a service or provider
    itself. The Sprint 9.1 conversation-history ``retrieve`` keeps working even
    when ``embeddings`` is ``None``, so the runtime pipeline is unaffected.
    """
    return MemoryRetrievalService(
        MessageRepository(session), embeddings, vector_store
    )


MemoryRetrievalServiceDep = Annotated[
    MemoryRetrievalService, Depends(get_memory_retrieval_service)
]


def get_ai_context_service(session: SessionDep) -> AIContextService:
    """Provide an :class:`AIContextService` bound to the session."""
    return AIContextService(session)


AIContextServiceDep = Annotated[
    AIContextService, Depends(get_ai_context_service)
]


def get_ai_context_engine_service(
    session: SessionDep,
    memory_retrieval: MemoryRetrievalServiceDep,
) -> AIContextEngineService:
    """Provide an :class:`AIContextEngineService` bound to the session.

    Sprint 7.1 runtime context assembler. Distinct from the Sprint 6C
    :class:`AIContextService`; composes existing services for loading and
    ownership. The Sprint 9.1 :class:`MemoryRetrievalService` is wired here
    (Sprint 9.2) via the existing ``get_memory_retrieval_service`` provider and
    injected into the engine — this is the only place it is constructed, so
    the engine never imports or constructs a repository itself.
    """
    return AIContextEngineService(session, memory_retrieval=memory_retrieval)


AIContextEngineServiceDep = Annotated[
    AIContextEngineService, Depends(get_ai_context_engine_service)
]


def get_prompt_builder_service() -> PromptBuilderService:
    """Provide a :class:`PromptBuilderService` (stateless, pure transform)."""
    return PromptBuilderService()


PromptBuilderServiceDep = Annotated[
    PromptBuilderService, Depends(get_prompt_builder_service)
]


def get_runtime_prompt_builder_service() -> RuntimePromptBuilderService:
    """Provide the Sprint 7.2 runtime prompt builder (stateless, pure transform).

    Builds a :class:`PromptPackage` from a ``RuntimeAIContext``. Distinct from
    the Sprint 6C :class:`PromptBuilderService` above; the unique class name
    removes the need for any import alias.
    """
    return RuntimePromptBuilderService()


RuntimePromptBuilderServiceDep = Annotated[
    RuntimePromptBuilderService, Depends(get_runtime_prompt_builder_service)
]


def get_conversation_context_service(
    session: SessionDep,
) -> ConversationContextService:
    """Provide a :class:`ConversationContextService` bound to the session."""
    return ConversationContextService(session)


def get_conversation_provider_factory() -> ConversationProviderFactory:
    """Provide the conversation provider factory (active-provider selector).

    Reads the Anthropic configuration from settings and hands it to the
    factory; the factory decides which concrete provider to return (currently
    always Claude). Swapping providers is a change confined to the factory,
    with no impact on services or routers.
    """
    return ConversationProviderFactory(
        api_key=settings.ANTHROPIC_API_KEY,
        model=settings.ANTHROPIC_MODEL,
        timeout=settings.ANTHROPIC_TIMEOUT_SECONDS,
        max_tokens=settings.ANTHROPIC_MAX_TOKENS,
    )


ConversationProviderFactoryDep = Annotated[
    ConversationProviderFactory, Depends(get_conversation_provider_factory)
]


def get_tool_provider() -> ToolProvider:
    """Provide the active tool provider (Sprint 11.1).

    Sprint 11.1 ships only the tool-execution framework — no concrete tool
    provider exists yet — so this composition-root seam is intentionally
    unfulfilled and raises. A later sprint registers real tool providers here
    (the one place providers are constructed), with no change required in
    :class:`ToolExecutionService` or its consumers.
    """
    raise NotImplementedError(
        "No tool provider is implemented yet (Sprint 11.1 ships only the "
        "execution framework); concrete providers are wired here in a later "
        "sprint."
    )


ToolProviderDep = Annotated[ToolProvider, Depends(get_tool_provider)]


def get_tool_execution_service(
    provider: ToolProviderDep,
) -> ToolExecutionService:
    """Provide a :class:`ToolExecutionService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — it is the Sprint 11.1 framework only.
    """
    return ToolExecutionService(provider)


ToolExecutionServiceDep = Annotated[
    ToolExecutionService, Depends(get_tool_execution_service)
]


def get_tool_providers() -> list[ToolProvider]:
    """Provide the registered tool providers (Sprint 11.2; empty for now).

    No concrete tool providers exist yet (Sprint 11.1's provider seam is
    unfulfilled), so this returns an empty list; a later sprint supplies the
    real providers here. Exposed as a sub-dependency so the composition root can
    resolve the registry even when it is reached through a route's dependency
    graph (Sprint 11.5 wires the registry into the AI orchestrator).
    """
    return []


ToolProvidersDep = Annotated[list[ToolProvider], Depends(get_tool_providers)]


def get_tool_registry(
    providers: ToolProvidersDep = None,
) -> ToolRegistry:
    """Provide a :class:`ToolRegistry` over the registered providers (11.2).

    ``providers`` is injected via the ``get_tool_providers`` sub-dependency
    (empty until a later sprint), so the registry defaults to empty. Constructor
    injection only — the registry is never instantiated inside a service.
    """
    return ToolRegistry(providers or [])


ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]


def get_permission_provider() -> PermissionProvider:
    """Provide the active permission provider (Sprint 11.3).

    Sprint 11.3 ships only the permission framework — no concrete permission
    provider exists yet — so this composition-root seam is intentionally
    unfulfilled and raises. A later sprint registers a real provider here (the
    one place providers are constructed), with no change required in
    :class:`PermissionService` or its consumers.
    """
    raise NotImplementedError(
        "No permission provider is implemented yet (Sprint 11.3 ships only the "
        "permission framework); a concrete provider is wired here in a later "
        "sprint."
    )


PermissionProviderDep = Annotated[
    PermissionProvider, Depends(get_permission_provider)
]


def get_permission_service(
    provider: PermissionProviderDep,
) -> PermissionService:
    """Provide a :class:`PermissionService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — it is the Sprint 11.3 framework only.
    """
    return PermissionService(provider)


PermissionServiceDep = Annotated[
    PermissionService, Depends(get_permission_service)
]


def get_planner_provider() -> PlannerProvider:
    """Provide the active planner provider (Sprint 11.4).

    Sprint 11.4 ships only the planning framework — no concrete planner provider
    exists yet — so this composition-root seam is intentionally unfulfilled and
    raises. A later sprint registers a real provider here (the one place
    providers are constructed), with no change required in :class:`PlannerService`
    or its consumers.
    """
    raise NotImplementedError(
        "No planner provider is implemented yet (Sprint 11.4 ships only the "
        "planning framework); a concrete provider is wired here in a later "
        "sprint."
    )


PlannerProviderDep = Annotated[
    PlannerProvider, Depends(get_planner_provider)
]


def get_planner_service(
    provider: PlannerProviderDep,
) -> PlannerService:
    """Provide a :class:`PlannerService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — it is the Sprint 11.4 framework only.
    """
    return PlannerService(provider)


PlannerServiceDep = Annotated[
    PlannerService, Depends(get_planner_service)
]


def get_planning_provider() -> PlanningProvider:
    """Provide the active planning provider (Sprint 13.1 — Planning Engine).

    Unlike the Sprint 11.3/11.4 framework seams (which raise until a provider
    exists), Sprint 13.1 ships a concrete, provider-independent default: the
    deterministic :class:`HeuristicPlanningProvider`, which reasons from the
    request text alone (no AI/SDK/network). Swapping in an LLM-backed planner
    later is a one-line change here, with no impact on the
    :class:`PlanningEngine` or its consumers.
    """
    return HeuristicPlanningProvider()


PlanningProviderDep = Annotated[
    PlanningProvider, Depends(get_planning_provider)
]


def get_plan_validator() -> PlanValidator:
    """Provide the stateless :class:`PlanValidator` (structural/logical checks)."""
    return PlanValidator()


PlanValidatorDep = Annotated[PlanValidator, Depends(get_plan_validator)]


def get_planning_explanation_builder() -> PlanningExplanationBuilder:
    """Provide the stateless :class:`PlanningExplanationBuilder` (narration)."""
    return PlanningExplanationBuilder()


PlanningExplanationBuilderDep = Annotated[
    PlanningExplanationBuilder, Depends(get_planning_explanation_builder)
]


def get_plan_analyzer() -> PlanAnalyzer:
    """Provide the stateless :class:`PlanAnalyzer` (Sprint 13.2).

    Deterministic, offline analysis of an :class:`ExecutionPlan` (readiness,
    confirmation, clarification, missing information, risk, confidence). No AI,
    network, SDK, session, or execution.
    """
    return PlanAnalyzer()


PlanAnalyzerDep = Annotated[PlanAnalyzer, Depends(get_plan_analyzer)]


def get_execution_preparation_engine() -> ExecutionPreparationEngine:
    """Provide the stateless :class:`ExecutionPreparationEngine` (Sprint 13.3).

    Deterministic, offline preparation of an :class:`ExecutionPlan` (required
    capabilities, external services, permissions, step count, execution strategy,
    and blockers). PREPARATION ONLY — no AI, network, SDK, Runtime, Registry,
    Permission, Tool execution, session, or execution.
    """
    return ExecutionPreparationEngine()


ExecutionPreparationEngineDep = Annotated[
    ExecutionPreparationEngine, Depends(get_execution_preparation_engine)
]


def get_decision_engine() -> DecisionEngine:
    """Provide the stateless :class:`DecisionEngine` (Sprint 13.4).

    Deterministic, offline classification of an :class:`ExecutionPlan` (plus its
    analysis and preparation) into an :class:`ExecutionDecision`. DECISION ONLY —
    no AI, network, SDK, Runtime, Registry, Permission, Tool execution, session,
    or execution.
    """
    return DecisionEngine()


DecisionEngineDep = Annotated[DecisionEngine, Depends(get_decision_engine)]


def get_execution_intent_engine() -> ExecutionIntentEngine:
    """Provide the stateless :class:`ExecutionIntentEngine` (Sprint 13.5).

    Deterministic, offline conversion of an :class:`ExecutionDecision` into an
    :class:`ExecutionIntent`. INTENT ONLY — no AI, network, SDK, Runtime,
    Session, Registry, Tool framework, Memory, Gemini, or execution.
    """
    return ExecutionIntentEngine()


ExecutionIntentEngineDep = Annotated[
    ExecutionIntentEngine, Depends(get_execution_intent_engine)
]


def get_execution_orchestrator() -> ExecutionOrchestrator:
    """Provide the stateless :class:`ExecutionOrchestrator` (Sprint 13.6).

    Deterministic, offline construction of an :class:`ExecutionWorkflow` from an
    :class:`ExecutionIntent` and its context. COORDINATION PLANNING ONLY — no AI,
    network, SDK, Runtime, Registry, Permission, Tool execution, Memory, Gemini,
    session, or execution.
    """
    return ExecutionOrchestrator()


ExecutionOrchestratorDep = Annotated[
    ExecutionOrchestrator, Depends(get_execution_orchestrator)
]


def get_execution_coordinator() -> ExecutionCoordinator:
    """Provide the stateless :class:`ExecutionCoordinator` (Sprint 13.7).

    Deterministic, offline conversion of an :class:`ExecutionWorkflow` into an
    :class:`ExecutionQueue`. ORGANISATION ONLY — no AI, network, SDK, Runtime,
    Session, Registry, Permission, Tool framework, Memory, Gemini, or execution.
    """
    return ExecutionCoordinator()


ExecutionCoordinatorDep = Annotated[
    ExecutionCoordinator, Depends(get_execution_coordinator)
]


def get_task_lifecycle_engine() -> TaskLifecycleEngine:
    """Provide the stateless :class:`TaskLifecycleEngine` (Sprint 13.8).

    Deterministic, offline construction of one :class:`TaskLifecycle` per
    execution unit in an :class:`ExecutionQueue`. STATE ONLY — no AI, network,
    SDK, Runtime, Session, Registry, Permission, Tool framework, Memory, Gemini,
    or execution.
    """
    return TaskLifecycleEngine()


TaskLifecycleEngineDep = Annotated[
    TaskLifecycleEngine, Depends(get_task_lifecycle_engine)
]


def get_execution_state_manager() -> ExecutionStateManager:
    """Provide the stateless :class:`ExecutionStateManager` (Sprint 13.9).

    Deterministic, offline aggregation of ``List[TaskLifecycle]`` into an
    :class:`ExecutionState`. STATE ONLY — no AI, network, SDK, Runtime, Session,
    Registry, Permission, Tool framework, Memory, Gemini, or execution.
    """
    return ExecutionStateManager()


ExecutionStateManagerDep = Annotated[
    ExecutionStateManager, Depends(get_execution_state_manager)
]


def get_execution_dependency_graph_builder() -> (
    ExecutionDependencyGraphBuilder
):
    """Provide the stateless :class:`ExecutionDependencyGraphBuilder` (13.10).

    Deterministic, offline construction of an :class:`ExecutionDependencyGraph`
    from an :class:`ExecutionQueue` and its lifecycles. RELATIONSHIPS ONLY — no
    AI, network, SDK, Runtime, Session, Registry, Permission, Tool framework,
    Memory, Gemini, or execution.
    """
    return ExecutionDependencyGraphBuilder()


ExecutionDependencyGraphBuilderDep = Annotated[
    ExecutionDependencyGraphBuilder,
    Depends(get_execution_dependency_graph_builder),
]


def get_execution_scheduler() -> ExecutionScheduler:
    """Provide the stateless :class:`ExecutionScheduler` (Sprint 13.11).

    Deterministic, offline construction of an :class:`ExecutionSchedule` from an
    :class:`ExecutionDependencyGraph` and an :class:`ExecutionState`. SCHEDULING
    ONLY — no AI, network, SDK, Runtime, Session, Registry, Permission, Tool
    framework, Memory, Gemini, or execution.
    """
    return ExecutionScheduler()


ExecutionSchedulerDep = Annotated[
    ExecutionScheduler, Depends(get_execution_scheduler)
]


def get_execution_monitor() -> ExecutionMonitor:
    """Provide the stateless :class:`ExecutionMonitor` (Sprint 13.12).

    Deterministic, offline construction of an :class:`ExecutionMonitoringReport`
    from an :class:`ExecutionSchedule` and an :class:`ExecutionState`.
    OBSERVATION ONLY — no AI, network, SDK, Runtime, Session, Registry,
    Permission, Tool framework, Memory, Gemini, or execution.
    """
    return ExecutionMonitor()


ExecutionMonitorDep = Annotated[
    ExecutionMonitor, Depends(get_execution_monitor)
]


def get_recovery_manager() -> RecoveryManager:
    """Provide the stateless :class:`RecoveryManager` (Sprint 13.13).

    Deterministic, offline construction of a :class:`RecoveryPlan` from an
    :class:`ExecutionMonitoringReport`, an :class:`ExecutionState`, and an
    :class:`ExecutionDependencyGraph`. RECOVERY PLANNING ONLY — no AI, network,
    SDK, Runtime, Session, Registry, Permission, Tool framework, Memory, Gemini,
    retries, or execution.
    """
    return RecoveryManager()


RecoveryManagerDep = Annotated[
    RecoveryManager, Depends(get_recovery_manager)
]


def get_human_approval_manager() -> HumanApprovalManager:
    """Provide the stateless :class:`HumanApprovalManager` (Sprint 13.14).

    Deterministic, offline construction of an :class:`ApprovalPlan` from an
    :class:`ExecutionIntent`, an :class:`ExecutionSchedule`, and a
    :class:`RecoveryPlan`. APPROVAL GOVERNANCE ONLY — no AI, network, SDK,
    Runtime, Session, Registry, Permission, Tool framework, Memory, Gemini,
    approval requests, or execution.
    """
    return HumanApprovalManager()


HumanApprovalManagerDep = Annotated[
    HumanApprovalManager, Depends(get_human_approval_manager)
]


def get_planning_engine(
    provider: PlanningProviderDep,
    validator: PlanValidatorDep,
    explanation_builder: PlanningExplanationBuilderDep,
    analyzer: PlanAnalyzerDep = None,
    preparation_engine: ExecutionPreparationEngineDep = None,
    decision_engine: DecisionEngineDep = None,
    intent_engine: ExecutionIntentEngineDep = None,
    orchestrator: ExecutionOrchestratorDep = None,
    coordinator: ExecutionCoordinatorDep = None,
    lifecycle_engine: TaskLifecycleEngineDep = None,
    state_manager: ExecutionStateManagerDep = None,
    dependency_graph_builder: ExecutionDependencyGraphBuilderDep = None,
    scheduler: ExecutionSchedulerDep = None,
    monitor: ExecutionMonitorDep = None,
    recovery_manager: RecoveryManagerDep = None,
    approval_manager: HumanApprovalManagerDep = None,
) -> PlanningEngine:
    """Provide the :class:`PlanningEngine` (plan -> analyze -> prepare -> decide -> intent -> workflow).

    Composes the injected planning provider, plan validator, explanation builder,
    (Sprint 13.2) the :class:`PlanAnalyzer`, (Sprint 13.3) the
    :class:`ExecutionPreparationEngine`, (Sprint 13.4) the
    :class:`DecisionEngine`, (Sprint 13.5) the
    :class:`ExecutionIntentEngine`, and (Sprint 13.6) the
    :class:`ExecutionOrchestrator` — constructor injection only; it instantiates
    nothing itself. The engine reasons, validates, analyses, prepares, decides,
    forms an execution intent, and coordinates a workflow but never executes and
    holds no session. The ``analyzer``, ``preparation_engine``,
    ``decision_engine``, ``intent_engine``, and ``orchestrator`` defaults of
    ``None`` keep earlier-sprint three-through-seven-argument construction working
    unchanged; FastAPI still resolves each via ``Depends`` when routed. Not yet
    wired into the Conversation Runtime — that integration belongs to a later
    sprint; this composition-root seam makes the engine resolvable and ready.
    """
    return PlanningEngine(
        provider,
        validator,
        explanation_builder,
        analyzer,
        preparation_engine,
        decision_engine,
        intent_engine,
        orchestrator,
        coordinator,
        lifecycle_engine,
        state_manager,
        dependency_graph_builder,
        scheduler,
        monitor,
        recovery_manager,
        approval_manager,
    )


PlanningEngineDep = Annotated[PlanningEngine, Depends(get_planning_engine)]


def get_execution_orchestration_engine() -> PlanningEngine:
    """Provide the fully-wired :class:`PlanningEngine` coordinator (Sprint 13.15).

    Integration seam only. Assembles the single orchestration coordinator by
    composing the already-existing collaborators through their existing
    composition-root providers (Sprint 13.1–13.14), so
    ``create_execution_orchestration`` can run the complete plan -> analyse ->
    prepare -> decide -> intent -> workflow -> queue -> lifecycles -> state ->
    dependency graph -> schedule -> monitoring report -> recovery plan ->
    approval plan pipeline. It adds no new behaviour and changes no existing
    provider — it is ``get_planning_engine`` with every collaborator supplied.
    """
    return get_planning_engine(
        get_planning_provider(),
        get_plan_validator(),
        get_planning_explanation_builder(),
        get_plan_analyzer(),
        get_execution_preparation_engine(),
        get_decision_engine(),
        get_execution_intent_engine(),
        get_execution_orchestrator(),
        get_execution_coordinator(),
        get_task_lifecycle_engine(),
        get_execution_state_manager(),
        get_execution_dependency_graph_builder(),
        get_execution_scheduler(),
        get_execution_monitor(),
        get_recovery_manager(),
        get_human_approval_manager(),
    )


ExecutionOrchestrationEngineDep = Annotated[
    PlanningEngine, Depends(get_execution_orchestration_engine)
]


def get_execution_runtime() -> ExecutionRuntime:
    """Provide the stateless :class:`ExecutionRuntime` (Sprint 14.1).

    Deterministic, offline creation of an :class:`ExecutionRuntimeContext` from a
    Sprint 13 :class:`ExecutionOrchestrationResult`. It owns the lifecycle of one
    execution session and only establishes runtime state. RUNTIME STATE ONLY —
    no AI, network, clock, UUID, SDK, dispatcher, capability knowledge, recovery,
    approval, or execution; it never mutates the orchestration.
    """
    return ExecutionRuntime()


ExecutionRuntimeDep = Annotated[
    ExecutionRuntime, Depends(get_execution_runtime)
]


def get_task_dispatcher() -> TaskDispatcher:
    """Provide the stateless :class:`TaskDispatcher` (Sprint 14.2).

    Deterministic, offline construction of a :class:`DispatchPlan` from an
    :class:`ExecutionRuntimeContext`. It reads the orchestration's execution
    queue and reports which units are eligible to leave the runtime. DISPATCH
    PLANNING ONLY — no AI, network, clock, UUID, SDK, capability knowledge,
    recovery, approval, Runtime global, or execution; it never mutates the
    runtime context or queue.
    """
    return TaskDispatcher()


TaskDispatcherDep = Annotated[
    TaskDispatcher, Depends(get_task_dispatcher)
]


def get_execution_capability() -> ExecutionCapability:
    """Provide the active execution capability (Sprint 14.3).

    Sprint 14.3 ships only the provider-independent execution-capability contract
    — no concrete capability exists yet — so this composition-root seam is
    intentionally unfulfilled and raises. A later sprint registers real
    capabilities here (the one place capabilities are constructed), with no change
    required in :class:`ExecutionCapability` or its consumers.
    """
    raise NotImplementedError(
        "No execution capability is implemented yet (Sprint 14.3 ships only the "
        "execution-capability contract); concrete capabilities are wired here in "
        "a later sprint."
    )


ExecutionCapabilityDep = Annotated[
    ExecutionCapability, Depends(get_execution_capability)
]


def get_capability_dispatcher() -> CapabilityDispatcher:
    """Provide the stateless :class:`CapabilityDispatcher` (Sprint 14.4).

    Deterministic, offline construction of a :class:`CapabilityDispatchPlan` from
    a :class:`DispatchPlan`. It routes each ready execution unit to a
    capability name and keeps unresolved units separate. ROUTING ONLY — no AI,
    network, clock, UUID, SDK, concrete capability, capability instantiation,
    registry, Runtime global, or execution; it never mutates the dispatch plan.
    """
    return CapabilityDispatcher()


CapabilityDispatcherDep = Annotated[
    CapabilityDispatcher, Depends(get_capability_dispatcher)
]


def get_capability_executor(
    capability: ExecutionCapabilityDep,
) -> CapabilityExecutor:
    """Provide a :class:`CapabilityExecutor` bound to the active capability (14.5).

    The :class:`ExecutionCapability` is injected from the composition root through
    the existing Sprint 14.3 seam (constructor injection); the executor never
    resolves or instantiates a capability itself. Until a concrete capability is
    wired, the seam raises ``NotImplementedError`` (so resolving this provider
    raises too), exactly like the other provider-backed services. Holds no
    session or mutable state and executes only through the interface.
    """
    return CapabilityExecutor(capability)


CapabilityExecutorDep = Annotated[
    CapabilityExecutor, Depends(get_capability_executor)
]


def get_execution_progress_runtime() -> ExecutionProgressRuntime:
    """Provide the stateless :class:`ExecutionProgressRuntime` (Sprint 14.6).

    Deterministic, offline aggregation of a :class:`CapabilityExecutionSummary`
    into an :class:`ExecutionProgress` — per-outcome counts, an overall status,
    and an integer completion percentage. PROGRESS TRACKING ONLY — no AI, network,
    clock, UUID, SDK, capability knowledge, routing, recovery, approval, Runtime
    global, or execution; it never mutates the summary.
    """
    return ExecutionProgressRuntime()


ExecutionProgressRuntimeDep = Annotated[
    ExecutionProgressRuntime, Depends(get_execution_progress_runtime)
]


def get_execution_controller() -> ExecutionController:
    """Provide the stateless :class:`ExecutionController` (Sprint 14.7).

    Deterministic, offline derivation of an :class:`ExecutionControlState` from an
    :class:`ExecutionProgress` — a control status plus the available pause/resume/
    cancel/restart actions. CONTROL REPRESENTATION ONLY — no AI, network, clock,
    UUID, SDK, capability knowledge, dispatch, recovery, approval, Runtime global,
    or execution; it never changes the execution progress.
    """
    return ExecutionController()


ExecutionControllerDep = Annotated[
    ExecutionController, Depends(get_execution_controller)
]


def get_execution_event_manager() -> ExecutionEventManager:
    """Provide the stateless :class:`ExecutionEventManager` (Sprint 14.8).

    Deterministic, offline generation of an :class:`ExecutionEventLog` from an
    :class:`ExecutionControlState` — one deterministic event representing the
    current runtime state, in an immutable history. EVENT RECORDING ONLY — no AI,
    network, clock, UUID, SDK, capability knowledge, dispatch, recovery, approval,
    Runtime global, or execution; it never changes the control state.
    """
    return ExecutionEventManager()


ExecutionEventManagerDep = Annotated[
    ExecutionEventManager, Depends(get_execution_event_manager)
]


def get_execution_lifecycle_manager() -> ExecutionLifecycleManager:
    """Provide the stateless :class:`ExecutionLifecycleManager` (Sprint 14.9).

    Deterministic, offline aggregation of an :class:`ExecutionEventLog` into a
    :class:`RuntimeExecutionLifecycle` — a lifecycle status, the preserved events,
    the current stage, and the terminal flag. LIFECYCLE REPRESENTATION ONLY — no
    AI, network, clock, UUID, SDK, capability knowledge, dispatch, recovery,
    approval, Runtime global, or execution; it never changes the event log.
    """
    return ExecutionLifecycleManager()


ExecutionLifecycleManagerDep = Annotated[
    ExecutionLifecycleManager, Depends(get_execution_lifecycle_manager)
]


def get_runtime_execution_state_manager() -> RuntimeExecutionStateManager:
    """Provide the stateless :class:`RuntimeExecutionStateManager` (Sprint 14.10).

    Deterministic, offline conversion of a :class:`RuntimeExecutionLifecycle` into
    a :class:`RuntimeExecutionState` — a state status, the current stage, and the
    active/terminal flags. RUNTIME STATE REPRESENTATION ONLY — no AI, network,
    clock, UUID, SDK, capability knowledge, dispatch, recovery, approval, Runtime
    global, or execution; it never changes the lifecycle.
    """
    return RuntimeExecutionStateManager()


RuntimeExecutionStateManagerDep = Annotated[
    RuntimeExecutionStateManager, Depends(get_runtime_execution_state_manager)
]


def get_runtime_execution_monitor() -> RuntimeExecutionMonitor:
    """Provide the stateless :class:`RuntimeExecutionMonitor` (Sprint 14.11).

    Deterministic, offline evaluation of a :class:`RuntimeExecutionState` into a
    :class:`RuntimeExecutionHealth` — a health status, a deterministic score, and
    any runtime warnings. HEALTH MONITORING ONLY — no AI, network, clock, UUID,
    SDK, capability knowledge, dispatch, recovery, approval, Runtime global, or
    execution; it never changes the runtime state.
    """
    return RuntimeExecutionMonitor()


RuntimeExecutionMonitorDep = Annotated[
    RuntimeExecutionMonitor, Depends(get_runtime_execution_monitor)
]


def get_runtime_pause_resume_manager() -> RuntimePauseResumeManager:
    """Provide the stateless :class:`RuntimePauseResumeManager` (Sprint 14.12).

    Deterministic, offline coordination of a :class:`RuntimeExecutionHealth` into
    a :class:`RuntimePauseResumeState` — a pause/resume status plus the pause/
    resume capabilities and the operator-action flag. COORDINATION ONLY — no AI,
    network, clock, UUID, SDK, capability knowledge, thread/process pausing,
    resumption, recovery, Runtime global, or execution; it never changes the
    runtime health.
    """
    return RuntimePauseResumeManager()


RuntimePauseResumeManagerDep = Annotated[
    RuntimePauseResumeManager, Depends(get_runtime_pause_resume_manager)
]


def get_runtime_recovery_coordinator() -> RuntimeRecoveryCoordinator:
    """Provide the stateless :class:`RuntimeRecoveryCoordinator` (Sprint 14.13).

    Deterministic, offline coordination of a :class:`RuntimePauseResumeState` into
    a :class:`RuntimeRecoveryState` — a recovery status, whether recovery is
    required, and the recovery strategy. RECOVERY COORDINATION ONLY — no AI,
    network, clock, UUID, SDK, capability knowledge, retry, resumption, planning,
    Runtime global, or execution; it never changes the pause/resume state.
    """
    return RuntimeRecoveryCoordinator()


RuntimeRecoveryCoordinatorDep = Annotated[
    RuntimeRecoveryCoordinator, Depends(get_runtime_recovery_coordinator)
]


def get_runtime_resource_coordinator() -> RuntimeResourceCoordinator:
    """Provide the stateless :class:`RuntimeResourceCoordinator` (Sprint 14.14).

    Deterministic, offline coordination of a :class:`RuntimeRecoveryState` into a
    :class:`RuntimeResourceState` — a resource status, a readiness flag, and the
    (currently empty) required resources. RESOURCE READINESS ONLY — no AI,
    network, clock, UUID, SDK, capability knowledge, allocation, reservation,
    planning, Runtime global, or execution; it never changes the recovery state.
    """
    return RuntimeResourceCoordinator()


RuntimeResourceCoordinatorDep = Annotated[
    RuntimeResourceCoordinator, Depends(get_runtime_resource_coordinator)
]


def get_runtime_execution_orchestrator(
    capability_executor: CapabilityExecutorDep,
) -> ExecutionRuntime:
    """Provide the fully-wired :class:`ExecutionRuntime` coordinator (Sprint 14.15).

    Integration seam only. Assembles the single runtime orchestration coordinator
    by composing the existing Sprint 14 runtime collaborators through their
    existing composition-root providers, so
    ``create_runtime_execution_orchestration`` can run the complete context ->
    dispatch -> capability dispatch -> execute -> progress -> control -> event ->
    lifecycle -> state -> health -> pause/resume -> recovery -> resource pipeline.
    The capability executor is injected through the existing Sprint 14.5 seam
    (constructor injection); until a concrete capability is wired, resolving it
    raises ``NotImplementedError`` like the other provider-backed services. It adds
    no new behaviour and changes no existing provider.
    """
    return ExecutionRuntime(
        task_dispatcher=get_task_dispatcher(),
        capability_dispatcher=get_capability_dispatcher(),
        capability_executor=capability_executor,
        progress_runtime=get_execution_progress_runtime(),
        controller=get_execution_controller(),
        event_manager=get_execution_event_manager(),
        lifecycle_manager=get_execution_lifecycle_manager(),
        state_manager=get_runtime_execution_state_manager(),
        monitor=get_runtime_execution_monitor(),
        pause_resume_manager=get_runtime_pause_resume_manager(),
        recovery_coordinator=get_runtime_recovery_coordinator(),
        resource_coordinator=get_runtime_resource_coordinator(),
    )


RuntimeExecutionOrchestratorDep = Annotated[
    ExecutionRuntime, Depends(get_runtime_execution_orchestrator)
]


def get_capability_definitions() -> list[CapabilityDefinition]:
    """Provide the registered capability definitions (Sprint 15.1; empty for now).

    No concrete capability definitions exist yet, so this returns an empty list;
    a later sprint supplies the real definitions here (the one composition-root
    place they are registered). Exposed as a sub-dependency so the registry can be
    resolved through a route's dependency graph, mirroring the Sprint 11.2 tool
    registry wiring.
    """
    return []


CapabilityDefinitionsDep = Annotated[
    list[CapabilityDefinition], Depends(get_capability_definitions)
]


def get_capability_registry(
    definitions: CapabilityDefinitionsDep = None,
) -> CapabilityRegistry:
    """Provide a :class:`CapabilityRegistry` over the registered definitions (15.1).

    ``definitions`` is injected via the ``get_capability_definitions``
    sub-dependency (empty until a later sprint), so the registry defaults to
    empty. Constructor injection only — the registry is never instantiated inside
    a service; it stores capability definitions and resolves, instantiates, and
    executes nothing. Purely additive; changes no existing provider.
    """
    return CapabilityRegistry(definitions or [])


CapabilityRegistryDep = Annotated[
    CapabilityRegistry, Depends(get_capability_registry)
]


def get_capability_resolver(
    registry: CapabilityRegistryDep,
) -> CapabilityResolver:
    """Provide a :class:`CapabilityResolver` bound to the capability registry (15.2).

    Reuses the existing Sprint 15.1 ``CapabilityRegistryDep`` (constructor
    injection); the resolver is never instantiated inside a service. It reads the
    registry only — it resolves capability definitions and executes, instantiates,
    and mutates nothing. Purely additive; changes no existing provider.
    """
    return CapabilityResolver(registry)


CapabilityResolverDep = Annotated[
    CapabilityResolver, Depends(get_capability_resolver)
]


def get_capability_metadata_manager(
    registry: CapabilityRegistryDep,
) -> CapabilityMetadataManager:
    """Provide a :class:`CapabilityMetadataManager` over the registry (15.3).

    Reuses the existing Sprint 15.1 ``CapabilityRegistryDep`` (constructor
    injection); the manager is never instantiated inside a service. It reads the
    registry only — it exposes structured metadata and executes, instantiates,
    and mutates nothing. Purely additive; changes no existing provider.
    """
    return CapabilityMetadataManager(registry)


CapabilityMetadataManagerDep = Annotated[
    CapabilityMetadataManager, Depends(get_capability_metadata_manager)
]


def get_capability_discovery_manager(
    metadata_manager: CapabilityMetadataManagerDep,
) -> CapabilityDiscoveryManager:
    """Provide a :class:`CapabilityDiscoveryManager` over the metadata (15.4).

    Reuses the existing Sprint 15.3 ``CapabilityMetadataManagerDep`` (constructor
    injection); the manager is never instantiated inside a service. It reads
    metadata only — it discovers capabilities and executes, resolves,
    instantiates, and mutates nothing. Purely additive; changes no existing
    provider.
    """
    return CapabilityDiscoveryManager(metadata_manager)


CapabilityDiscoveryManagerDep = Annotated[
    CapabilityDiscoveryManager, Depends(get_capability_discovery_manager)
]


def get_capability_validation_manager() -> CapabilityValidationManager:
    """Provide the stateless :class:`CapabilityValidationManager` (Sprint 15.5).

    Deterministic, offline validation of a capability invocation request against
    its declared metadata. It holds no collaborator, session, or state — it reads
    the request only and validates, executes, resolves, and mutates nothing.
    Purely additive; changes no existing provider.
    """
    return CapabilityValidationManager()


CapabilityValidationManagerDep = Annotated[
    CapabilityValidationManager, Depends(get_capability_validation_manager)
]


def get_browser_dom() -> BrowserDOM:
    """Provide the stateless :class:`BrowserDOM` DOM collaborator (Sprint 15.7).

    Deterministic, offline DOM reader/query engine over plain HTML (stdlib parser,
    no browser/SDK). It holds no state and is injected into the
    :class:`BrowserCapability`, which delegates DOM discovery to it. Purely
    additive.
    """
    return BrowserDOM()


BrowserDOMDep = Annotated[BrowserDOM, Depends(get_browser_dom)]


def get_browser_interaction() -> BrowserInteraction:
    """Provide the stateless :class:`BrowserInteraction` collaborator (Sprint 15.8).

    Deterministic performer of click/type/scroll/focus/select on a
    :class:`BrowserElement`; it holds no state and delegates the low-level action
    to the capability's :class:`BrowserDriver` (the only Playwright-facing layer),
    turning provider failures into graceful results. Injected into the
    :class:`BrowserCapability`. Purely additive.
    """
    return BrowserInteraction()


BrowserInteractionDep = Annotated[
    BrowserInteraction, Depends(get_browser_interaction)
]


def get_browser_workspace() -> BrowserWorkspace:
    """Provide the stateless :class:`BrowserWorkspace` collaborator (Sprint 15.9).

    Deterministic manager of browser tabs, screenshots, PDF, downloads, uploads,
    and cookie save/load; it holds no state, transforms immutable workspace DTOs
    for tab actions, and delegates I/O actions to the capability's
    :class:`BrowserDriver` (the only Playwright-facing layer), turning provider
    failures into graceful results. Injected into the :class:`BrowserCapability`.
    Purely additive.
    """
    return BrowserWorkspace()


BrowserWorkspaceDep = Annotated[
    BrowserWorkspace, Depends(get_browser_workspace)
]


def get_browser_capability(
    browser_dom: BrowserDOMDep = None,
    browser_interaction: BrowserInteractionDep = None,
    browser_workspace: BrowserWorkspaceDep = None,
) -> BrowserCapability:
    """Provide the :class:`BrowserCapability` — the first real capability (15.6).

    Constructs a Playwright/Chromium-backed :class:`PlaywrightBrowserDriver` (the
    SDK is imported lazily on first navigation, so building this provider needs no
    browser installed) and injects it into the :class:`BrowserCapability`, which
    implements the Sprint 14.3 :class:`ExecutionCapability` interface. Sprint 15.7
    injects the :class:`BrowserDOM` collaborator and Sprint 15.8 the
    :class:`BrowserInteraction` collaborator (each via its Dep, defaulting to a
    fresh one) so the capability can delegate DOM discovery and interactions.
    Purely additive: it introduces new capability seams and does not change the
    existing ``get_execution_capability`` placeholder or any Runtime/Planning
    wiring.
    """
    return BrowserCapability(
        PlaywrightBrowserDriver(headless=True),
        timeout_ms=DEFAULT_NAVIGATION_TIMEOUT_MS,
        browser_dom=browser_dom or get_browser_dom(),
        browser_interaction=browser_interaction or get_browser_interaction(),
        browser_workspace=browser_workspace or get_browser_workspace(),
    )


BrowserCapabilityDep = Annotated[
    BrowserCapability, Depends(get_browser_capability)
]


def get_python_capability() -> PythonCapability:
    """Provide the :class:`PythonCapability` — the Python capability (Sprint 15.10).

    Assembles the capability with its default collaborators (a
    :class:`SafePythonExecutor` sandbox, a :class:`PythonArtifactManager`, and a
    :class:`PythonWorkspaceManager`); the safe executor imports third-party
    libraries lazily, so building this provider needs none of numpy/pandas/openpyxl/
    matplotlib installed. It implements the Sprint 14.3
    :class:`ExecutionCapability` interface. Purely additive: it introduces a new
    capability seam and does not change the existing ``get_execution_capability``
    placeholder or any Runtime/Planning/Browser wiring.
    """
    return PythonCapability()


PythonCapabilityDep = Annotated[
    PythonCapability, Depends(get_python_capability)
]


def get_filesystem_capability() -> FileSystemCapability:
    """Provide the :class:`FileSystemCapability` — the filesystem capability (15.11).

    Assembles the capability with its default collaborators (a
    :class:`LocalFileSystemExecutor` confined to the workspace root, a
    :class:`FileSystemArtifactManager`, and a :class:`FileSystemWorkspaceManager`);
    the executor uses only the Python standard library, so building this provider
    needs no external SDK. It implements the Sprint 14.3
    :class:`ExecutionCapability` interface. Purely additive: it introduces a new
    capability seam and does not change the existing ``get_execution_capability``
    placeholder or any Runtime/Planning/Browser/Python wiring.
    """
    return FileSystemCapability()


FileSystemCapabilityDep = Annotated[
    FileSystemCapability, Depends(get_filesystem_capability)
]


def get_email_capability() -> EmailCapability:
    """Provide the :class:`EmailCapability` — the email capability (Sprint 15.12).

    Assembles the capability with its default collaborators (a
    :class:`LocalEmailExecutor` in-memory mailbox, an :class:`EmailArtifactManager`,
    and an :class:`EmailWorkspaceManager`); the local executor uses only the Python
    standard library and holds no credential, so building this provider needs no
    external SDK or mail server. Swapping in a real provider (Gmail API, Microsoft
    Graph, IMAP, SMTP, Exchange) is a one-line change here — inject a different
    :class:`EmailExecutor` — with no impact on the capability or the Runtime. It
    implements the Sprint 14.3 :class:`ExecutionCapability` interface. Purely
    additive: it introduces a new capability seam and does not change the existing
    ``get_execution_capability`` placeholder or any Runtime/Planning/Browser/Python/
    File System wiring.
    """
    return EmailCapability()


EmailCapabilityDep = Annotated[
    EmailCapability, Depends(get_email_capability)
]


def get_calendar_capability() -> CalendarCapability:
    """Provide the :class:`CalendarCapability` — the calendar capability (Sprint 15.13).

    Assembles the capability with its default collaborators (a
    :class:`LocalCalendarExecutor` in-memory calendar, a
    :class:`CalendarArtifactManager`, and a :class:`CalendarWorkspaceManager`); the
    local executor uses only the Python standard library and holds no credential, so
    building this provider needs no external SDK or calendar server. Swapping in a
    real provider (Google Calendar, Microsoft Graph, Outlook, Exchange, Apple
    Calendar, CalDAV) is a one-line change here — inject a different
    :class:`CalendarExecutor` — with no impact on the capability or the Runtime. It
    implements the Sprint 14.3 :class:`ExecutionCapability` interface. Purely
    additive: it introduces a new capability seam and does not change the existing
    ``get_execution_capability`` placeholder or any Runtime/Planning/Browser/Python/
    File System/Email wiring.
    """
    return CalendarCapability()


CalendarCapabilityDep = Annotated[
    CalendarCapability, Depends(get_calendar_capability)
]


def get_github_capability() -> GitHubCapability:
    """Provide the :class:`GitHubCapability` — the GitHub capability (Sprint 15.14).

    Assembles the capability with its default collaborators (a
    :class:`LocalGitExecutor` in-memory Git simulation, a
    :class:`GitHubArtifactManager`, and a :class:`GitHubWorkspaceManager`); the local
    executor uses only the Python standard library and holds no credential, so
    building this provider needs no external SDK, git binary, or network. Swapping in
    a real provider (GitHub REST/GraphQL, Git CLI, GitLab, Bitbucket, Azure DevOps) is
    a one-line change here — inject a different :class:`GitHubExecutor` — with no
    impact on the capability or the Runtime. It implements the Sprint 14.3
    :class:`ExecutionCapability` interface. Purely additive: it introduces a new
    capability seam and does not change the existing ``get_execution_capability``
    placeholder or any Runtime/Planning/Browser/Python/File System/Email/Calendar
    wiring.
    """
    return GitHubCapability()


GitHubCapabilityDep = Annotated[
    GitHubCapability, Depends(get_github_capability)
]


def get_capability_router(
    browser: BrowserCapabilityDep = None,
    python: PythonCapabilityDep = None,
    filesystem: FileSystemCapabilityDep = None,
    email: EmailCapabilityDep = None,
    calendar: CalendarCapabilityDep = None,
    github: GitHubCapabilityDep = None,
) -> CapabilityRouter:
    """Provide the :class:`CapabilityRouter` over the Sprint 15 capabilities (15.15).

    Composes the six existing capability providers — Browser (15.6), Python (15.10),
    File System (15.11), Email (15.12), Calendar (15.13), and GitHub (15.14) — into a
    name→:class:`ExecutionCapability` mapping (constructor injection; the router
    instantiates nothing itself). Each is resolved through its own existing provider,
    so no capability wiring changes. The router only knows the Sprint 14.3
    :class:`ExecutionCapability` contract, so providers plug in behind a name without
    the router changing. Purely additive.
    """
    return CapabilityRouter(
        {
            "browser": browser or get_browser_capability(),
            "python": python or get_python_capability(),
            "filesystem": filesystem or get_filesystem_capability(),
            "email": email or get_email_capability(),
            "calendar": calendar or get_calendar_capability(),
            "github": github or get_github_capability(),
        }
    )


CapabilityRouterDep = Annotated[
    CapabilityRouter, Depends(get_capability_router)
]


def get_artifact_coordinator() -> ArtifactCoordinator:
    """Provide the stateless :class:`ArtifactCoordinator` (Sprint 15.15).

    Deterministic, offline extractor of shared :class:`WorkflowArtifactReference`
    records from a capability's plain outputs — it holds no state, reads no file
    contents, and exposes no provider object. Purely additive.
    """
    return ArtifactCoordinator()


ArtifactCoordinatorDep = Annotated[
    ArtifactCoordinator, Depends(get_artifact_coordinator)
]


def get_workflow_coordinator(
    router: CapabilityRouterDep = None,
    artifact_coordinator: ArtifactCoordinatorDep = None,
) -> WorkflowCoordinator:
    """Provide the :class:`WorkflowCoordinator` — sequential multi-capability runner (15.15).

    Composes the injected :class:`CapabilityRouter` (over the six Sprint 15
    capabilities) and the :class:`ArtifactCoordinator` (constructor injection; it
    instantiates neither). It executes a given list of :class:`WorkflowStep` records,
    threading outputs and artifacts between capabilities and stopping on the first
    failure. It performs no planning and no AI autonomy — Planning produces the steps
    in an earlier layer. Purely additive: it introduces a new coordination seam and
    changes no existing capability, Runtime, or Planning wiring.
    """
    return WorkflowCoordinator(
        router or get_capability_router(),
        artifact_coordinator or get_artifact_coordinator(),
    )


WorkflowCoordinatorDep = Annotated[
    WorkflowCoordinator, Depends(get_workflow_coordinator)
]


def get_ai_employee(
    planning_engine: PlanningEngineDep = None,
    workflow_coordinator: WorkflowCoordinatorDep = None,
) -> AIEmployee:
    """Provide the :class:`AIEmployee` — the AI Employee Foundation (Sprint 16.1).

    Composes the injected Sprint 13 :class:`PlanningEngine` and the Sprint 15.15
    :class:`WorkflowCoordinator` (constructor injection; it instantiates neither).
    The foundation owns employee sessions and task delegation and orchestrates
    those two collaborators through their existing public contracts — it plans
    nothing, executes no capability, and never touches Runtime, Memory,
    Permission, or Capability internals directly. When called outside a FastAPI
    request the ``= None`` defaults fall back to the fully-wired
    ``get_execution_orchestration_engine`` (a ready :class:`PlanningEngine`) and
    ``get_workflow_coordinator``, both callable with no arguments. Purely
    additive: it introduces a new foundation seam and changes no existing
    Planning, Runtime, Workflow, or capability wiring.
    """
    return AIEmployee(
        planning_engine or get_execution_orchestration_engine(),
        workflow_coordinator or get_workflow_coordinator(),
    )


AIEmployeeDep = Annotated[AIEmployee, Depends(get_ai_employee)]


def get_progress_tracker() -> ProgressTracker:
    """Provide the stateless :class:`ProgressTracker` (Sprint 16.2).

    Deterministic, offline derivation of a :class:`WorkflowProgress` from a step
    count or a Sprint 15.15 :class:`WorkflowExecutionResult`. It holds no state and
    executes, dispatches, and mutates nothing. Purely additive.
    """
    return ProgressTracker()


ProgressTrackerDep = Annotated[ProgressTracker, Depends(get_progress_tracker)]


def get_approval_manager() -> ApprovalManager:
    """Provide the basic :class:`ApprovalManager` — :class:`AutoApprovalPolicy` (16.2).

    The abstraction lets a later Sprint 16.x policy swap in behind
    ``requires_approval``/``approve``/``reject`` with no change to the lifecycle
    manager; the Sprint 16.2 default auto-approves every job and never gates a run.
    Stateless, deterministic; no UI, voice, mobile, or permission system. Purely
    additive.
    """
    return AutoApprovalPolicy()


ApprovalManagerDep = Annotated[ApprovalManager, Depends(get_approval_manager)]


def get_notification_manager() -> NotificationManager:
    """Provide the basic :class:`NotificationManager` — in-memory store (16.2).

    The abstraction lets a later Sprint 16.x implementation (push, email, webhook)
    swap in behind ``record``/``notifications`` with no change to the lifecycle
    manager; the Sprint 16.2 default stores notifications in memory and delivers
    none. Deterministic; each request resolves a fresh store. Purely additive.
    """
    return InMemoryNotificationManager()


NotificationManagerDep = Annotated[
    NotificationManager, Depends(get_notification_manager)
]


def get_workflow_recovery_manager() -> WorkflowRecoveryManager:
    """Provide the basic workflow :class:`RecoveryManager` — bounded retries (16.2).

    Named ``workflow`` to stay distinct from the Sprint 13 planning
    :class:`RecoveryManager`. The abstraction lets a later Sprint 16.x policy swap
    in behind ``can_retry``/``retry``/``abort`` with no change to the lifecycle
    manager; the Sprint 16.2 default allows a bounded number of whole-job retries
    and no advanced recovery. Stateless, deterministic. Purely additive.
    """
    return BasicRecoveryManager()


WorkflowRecoveryManagerDep = Annotated[
    WorkflowRecoveryManager, Depends(get_workflow_recovery_manager)
]


def get_persistence_manager() -> PersistenceManager:
    """Provide the basic :class:`PersistenceManager` — in-memory store (16.2).

    The abstraction lets a later Sprint 16.x implementation (PostgreSQL, Redis,
    file) swap in behind ``save_instance``/``load_instance``/``delete_instance``
    with no change to the lifecycle manager; the Sprint 16.2 default keeps instances
    in a deterministic in-memory dictionary with no database or file I/O. Each
    request resolves a fresh store. Purely additive.
    """
    return InMemoryPersistenceManager()


PersistenceManagerDep = Annotated[
    PersistenceManager, Depends(get_persistence_manager)
]


def get_workflow_lifecycle_manager(
    planning_engine: PlanningEngineDep = None,
    workflow_coordinator: WorkflowCoordinatorDep = None,
    progress_tracker: ProgressTrackerDep = None,
    approval_manager: ApprovalManagerDep = None,
    notification_manager: NotificationManagerDep = None,
    recovery_manager: WorkflowRecoveryManagerDep = None,
    persistence_manager: PersistenceManagerDep = None,
) -> WorkflowLifecycleManager:
    """Provide the :class:`WorkflowLifecycleManager` — the Execution Platform (16.2).

    Composes the injected Sprint 13 :class:`PlanningEngine`, the Sprint 15.15
    :class:`WorkflowCoordinator`, and the five Sprint 16.2 managers
    (:class:`ProgressTracker`, :class:`ApprovalManager`,
    :class:`NotificationManager`, workflow :class:`RecoveryManager`,
    :class:`PersistenceManager`) — constructor injection; it instantiates none of
    them. The lifecycle manager owns a delegated job's life (create, start, pause,
    resume, cancel, retry, complete, fail, run) and reaches capabilities only
    through the Workflow Coordinator — never importing a capability module. When
    called outside a FastAPI request the ``= None`` defaults fall back to the
    fully-wired ``get_execution_orchestration_engine`` and ``get_workflow_coordinator``
    plus fresh managers, all callable with no arguments. Purely additive: it
    introduces a new coordination seam and changes no existing wiring.
    """
    return WorkflowLifecycleManager(
        planning_engine or get_execution_orchestration_engine(),
        workflow_coordinator or get_workflow_coordinator(),
        progress_tracker or get_progress_tracker(),
        approval_manager or get_approval_manager(),
        notification_manager or get_notification_manager(),
        recovery_manager or get_workflow_recovery_manager(),
        persistence_manager or get_persistence_manager(),
    )


WorkflowLifecycleManagerDep = Annotated[
    WorkflowLifecycleManager, Depends(get_workflow_lifecycle_manager)
]


def get_approval_risk_model() -> approval_engine.RiskModel:
    """Provide the configurable :class:`RiskModel` — action → risk (Sprint 16.3).

    Deterministic, offline assessment of a requested action's
    :class:`ApprovalRiskLevel` from the default (override-able) mapping. It holds no
    workflow state and executes nothing. Purely additive.
    """
    return approval_engine.RiskModel()


ApprovalRiskModelDep = Annotated[
    approval_engine.RiskModel, Depends(get_approval_risk_model)
]


def get_approval_policy() -> approval_engine.ApprovalPolicy:
    """Provide the default approval policy — :class:`RiskBasedApprovalPolicy` (16.3).

    The production default gates on risk (approval required at or above ``HIGH``);
    the abstraction lets :class:`AutoApprovalPolicy` or a later Sprint 16.x policy
    swap in with no change to the engine. Stateless, deterministic. Purely
    additive.
    """
    return approval_engine.RiskBasedApprovalPolicy()


ApprovalPolicyDep = Annotated[
    approval_engine.ApprovalPolicy, Depends(get_approval_policy)
]


def get_approval_queue() -> approval_engine.ApprovalQueueManager:
    """Provide the deterministic in-memory :class:`ApprovalQueueManager` (16.3).

    Holds pending approval requests in enqueue order with no background worker;
    each request resolves a fresh queue. Purely additive.
    """
    return approval_engine.ApprovalQueueManager()


ApprovalQueueDep = Annotated[
    approval_engine.ApprovalQueueManager, Depends(get_approval_queue)
]


def get_approval_engine(
    policy: ApprovalPolicyDep = None,
    risk_model: ApprovalRiskModelDep = None,
    queue: ApprovalQueueDep = None,
) -> approval_engine.ApprovalManager:
    """Provide the Sprint 16.3 :class:`ApprovalManager` engine — approval entry point.

    Composes the injected approval policy, configurable risk model, and in-memory
    queue (constructor injection; it instantiates none of them). The engine
    coordinates the approval flow only — it executes no workflow, no capability, and
    persists no workflow. When called outside a FastAPI request the ``= None``
    defaults fall back to the fresh provider instances, all callable with no
    arguments. Purely additive: a new approval seam that changes no existing wiring.
    """
    return approval_engine.ApprovalManager(
        policy or get_approval_policy(),
        risk_model or get_approval_risk_model(),
        queue or get_approval_queue(),
    )


ApprovalEngineDep = Annotated[
    approval_engine.ApprovalManager, Depends(get_approval_engine)
]


def get_approval_workflow_coordinator(
    lifecycle_manager: WorkflowLifecycleManagerDep = None,
    engine: ApprovalEngineDep = None,
) -> approval_engine.ApprovalWorkflowCoordinator:
    """Provide the :class:`ApprovalWorkflowCoordinator` — approval↔workflow (16.3).

    Composes the frozen Sprint 16.2 :class:`WorkflowLifecycleManager` and the Sprint
    16.3 :class:`ApprovalManager` engine (constructor injection; it instantiates
    neither). It maps approval outcomes to the lifecycle manager's existing
    ``pause``/``resume``/``cancel`` transitions — pause when approval is required,
    resume on approval, cancel on rejection — redesigning neither frozen component.
    When called outside a FastAPI request the ``= None`` defaults fall back to the
    fully-wired providers. Purely additive.
    """
    return approval_engine.ApprovalWorkflowCoordinator(
        lifecycle_manager or get_workflow_lifecycle_manager(),
        engine or get_approval_engine(),
    )


ApprovalWorkflowCoordinatorDep = Annotated[
    approval_engine.ApprovalWorkflowCoordinator,
    Depends(get_approval_workflow_coordinator),
]


def get_notification_priority_model() -> notification_engine.PriorityModel:
    """Provide the configurable :class:`PriorityModel` — event → priority (16.4).

    Deterministic, offline assignment of a notification event's
    :class:`NotificationPriority` from the default (override-able) mapping. It holds
    no workflow state and executes nothing. Purely additive.
    """
    return notification_engine.PriorityModel()


NotificationPriorityModelDep = Annotated[
    notification_engine.PriorityModel, Depends(get_notification_priority_model)
]


def get_notification_policy() -> notification_engine.NotificationPolicy:
    """Provide the default notification policy — :class:`ImmediateNotificationPolicy` (16.4).

    The default dispatches each notification as it is created; the abstraction lets
    :class:`BatchedNotificationPolicy` or a later Sprint 16.x policy swap in with no
    change to the engine. Stateless, deterministic. Purely additive.
    """
    return notification_engine.ImmediateNotificationPolicy()


NotificationPolicyDep = Annotated[
    notification_engine.NotificationPolicy, Depends(get_notification_policy)
]


def get_notification_queue() -> notification_engine.NotificationQueue:
    """Provide the deterministic in-memory priority :class:`NotificationQueue` (16.4).

    Orders queued notifications by priority (``CRITICAL`` → ``LOW``, FIFO within a
    priority) with no background worker; each request resolves a fresh queue.
    Purely additive.
    """
    return notification_engine.NotificationQueue()


NotificationQueueDep = Annotated[
    notification_engine.NotificationQueue, Depends(get_notification_queue)
]


def get_notification_dispatcher() -> notification_engine.NotificationDispatcher:
    """Provide the basic :class:`NotificationDispatcher` — in-memory (16.4).

    The abstraction is the seam a later Sprint 16.x delivery channel plugs into;
    the Sprint 16.4 default records dispatched/delivered notifications in memory and
    delivers nothing externally (no Email/Slack/Teams/Discord/SMS/Push/WebSocket).
    Each request resolves a fresh dispatcher. Purely additive.
    """
    return notification_engine.InMemoryNotificationDispatcher()


NotificationDispatcherDep = Annotated[
    notification_engine.NotificationDispatcher,
    Depends(get_notification_dispatcher),
]


def get_notification_history() -> notification_engine.NotificationHistory:
    """Provide the deterministic in-memory :class:`NotificationHistory` store (16.4).

    Records immutable notification history and answers find-by-workflow/type/status
    queries with no background worker; each request resolves a fresh store. Purely
    additive.
    """
    return notification_engine.NotificationHistory()


NotificationHistoryDep = Annotated[
    notification_engine.NotificationHistory, Depends(get_notification_history)
]


def get_notification_engine(
    policy: NotificationPolicyDep = None,
    queue: NotificationQueueDep = None,
    dispatcher: NotificationDispatcherDep = None,
    history: NotificationHistoryDep = None,
    priority_model: NotificationPriorityModelDep = None,
) -> notification_engine.NotificationManager:
    """Provide the Sprint 16.4 :class:`NotificationManager` engine.

    Composes the injected notification policy, priority queue, in-memory dispatcher,
    history store, and configurable priority model (constructor injection; it
    instantiates none of them). The engine coordinates the notification lifecycle
    only — it executes no workflow, no capability, and delivers nothing externally.
    When called outside a FastAPI request the ``= None`` defaults fall back to the
    fresh provider instances, all callable with no arguments. Purely additive: a new
    notification seam that changes no existing wiring.
    """
    return notification_engine.NotificationManager(
        policy or get_notification_policy(),
        queue or get_notification_queue(),
        dispatcher or get_notification_dispatcher(),
        history or get_notification_history(),
        priority_model or get_notification_priority_model(),
    )


NotificationEngineDep = Annotated[
    notification_engine.NotificationManager, Depends(get_notification_engine)
]


def get_notification_workflow_coordinator(
    lifecycle_manager: WorkflowLifecycleManagerDep = None,
    engine: NotificationEngineDep = None,
) -> notification_engine.NotificationWorkflowCoordinator:
    """Provide the :class:`NotificationWorkflowCoordinator` — notification↔workflow (16.4).

    Composes the frozen Sprint 16.2 :class:`WorkflowLifecycleManager` and the Sprint
    16.4 :class:`NotificationManager` engine (constructor injection; it instantiates
    neither). It records a mapped notification from each lifecycle transition
    (``start``/``pause``/``resume``/``cancel``/``complete``/``fail``), redesigning
    neither frozen component and delivering nothing externally. When called outside
    a FastAPI request the ``= None`` defaults fall back to the fully-wired providers.
    Purely additive.
    """
    return notification_engine.NotificationWorkflowCoordinator(
        lifecycle_manager or get_workflow_lifecycle_manager(),
        engine or get_notification_engine(),
    )


NotificationWorkflowCoordinatorDep = Annotated[
    notification_engine.NotificationWorkflowCoordinator,
    Depends(get_notification_workflow_coordinator),
]


def get_persistence_repository() -> persistence_engine.PersistenceRepository:
    """Provide the basic :class:`PersistenceRepository` — in-memory store (16.5).

    The abstraction is the seam a later Sprint 16.x storage provider plugs into; the
    Sprint 16.5 default keeps versioned snapshots in a deterministic in-memory
    dictionary with no database, SQLite, PostgreSQL, Redis, or cloud storage. The
    repository owns storage; each request resolves a fresh one. Purely additive.
    """
    return persistence_engine.InMemoryPersistenceRepository()


PersistenceRepositoryDep = Annotated[
    persistence_engine.PersistenceRepository,
    Depends(get_persistence_repository),
]


def get_persistence_engine(
    repository: PersistenceRepositoryDep = None,
) -> persistence_engine.PersistenceManager:
    """Provide the Sprint 16.5 :class:`PersistenceManager` engine.

    Composes the injected :class:`PersistenceRepository` (constructor injection; it
    instantiates none). The engine owns persistence *decisions* — versioning,
    snapshotting, and validation — and delegates all storage to the repository; it
    executes no workflow, no capability, and contains no storage logic. When called
    outside a FastAPI request the ``= None`` default falls back to a fresh in-memory
    repository. Purely additive: a new persistence seam that changes no existing
    wiring.
    """
    return persistence_engine.PersistenceManager(
        repository or get_persistence_repository()
    )


PersistenceEngineDep = Annotated[
    persistence_engine.PersistenceManager, Depends(get_persistence_engine)
]


def get_memory_policy() -> memory_engine.MemoryPolicy:
    """Provide the default memory policy — :class:`RuleBasedMemoryPolicy` (16.6).

    The default remembers every category except transient notifications; the
    abstraction lets a later Sprint 16.x policy swap in with no change to the
    orchestrator. Stateless, deterministic. Purely additive.
    """
    return memory_engine.RuleBasedMemoryPolicy()


MemoryPolicyDep = Annotated[
    memory_engine.MemoryPolicy, Depends(get_memory_policy)
]


def get_memory_classifier() -> memory_engine.MemoryClassifier:
    """Provide the default memory classifier — :class:`RuleBasedMemoryClassifier` (16.6).

    The default maps preferences/system to ``PERMANENT``, workflow/task results to
    ``LONG_TERM``, approvals to ``SHORT_TERM``, and notifications to ``TEMPORARY``;
    the mapping is configurable. Stateless, deterministic. Purely additive.
    """
    return memory_engine.RuleBasedMemoryClassifier()


MemoryClassifierDep = Annotated[
    memory_engine.MemoryClassifier, Depends(get_memory_classifier)
]


def get_memory_retriever() -> memory_engine.MemoryRetriever:
    """Provide the deterministic in-memory :class:`MemoryRetriever` index (16.6).

    Holds the memory index and retrieves with exact filters (workflow/category/
    priority/tag/latest) — no embeddings, vectors, or semantic search — with no
    background worker; each request resolves a fresh index. Purely additive.
    """
    return memory_engine.MemoryRetriever()


MemoryRetrieverDep = Annotated[
    memory_engine.MemoryRetriever, Depends(get_memory_retriever)
]


def get_memory_orchestrator(
    policy: MemoryPolicyDep = None,
    classifier: MemoryClassifierDep = None,
    retriever: MemoryRetrieverDep = None,
    persistence: PersistenceEngineDep = None,
) -> memory_engine.MemoryOrchestrator:
    """Provide the Sprint 16.6 :class:`MemoryOrchestrator`.

    Composes the injected memory policy, classifier, retriever, and the Sprint 16.5
    :class:`PersistenceManager` (constructor injection; it instantiates none of
    them). The orchestrator decides what to remember/retrieve and always routes
    durable workflow-state storage through the Persistence Layer — it stores no
    record itself, touches no repository or database, and executes no workflow. When
    called outside a FastAPI request the ``= None`` defaults fall back to fresh
    provider instances. Purely additive: a new memory seam that changes no existing
    wiring.
    """
    return memory_engine.MemoryOrchestrator(
        policy or get_memory_policy(),
        classifier or get_memory_classifier(),
        retriever or get_memory_retriever(),
        persistence or get_persistence_engine(),
    )


MemoryOrchestratorDep = Annotated[
    memory_engine.MemoryOrchestrator, Depends(get_memory_orchestrator)
]


def get_schedule_policy() -> scheduler_engine.SchedulePolicy:
    """Provide the default schedule policy — :class:`RequestSchedulePolicy` (16.7).

    The default respects each request's own schedule type; the abstraction lets
    :class:`ImmediatePolicy`/:class:`DelayedPolicy`/:class:`RecurringPolicy` or a
    later Sprint 16.x policy swap in with no change to the manager. Stateless,
    deterministic. Purely additive.
    """
    return scheduler_engine.RequestSchedulePolicy()


SchedulePolicyDep = Annotated[
    scheduler_engine.SchedulePolicy, Depends(get_schedule_policy)
]


def get_schedule_planner() -> scheduler_engine.SchedulePlanner:
    """Provide the deterministic :class:`SchedulePlanner` (Sprint 16.7).

    Computes next-execution *ticks* for IMMEDIATE/DELAYED/AT_TIME/RECURRING from a
    caller-supplied tick — no wall-clock, timer, or sleep. Stateless. Purely
    additive.
    """
    return scheduler_engine.SchedulePlanner()


SchedulePlannerDep = Annotated[
    scheduler_engine.SchedulePlanner, Depends(get_schedule_planner)
]


def get_schedule_queue() -> scheduler_engine.ScheduleQueue:
    """Provide the deterministic tick-ordered :class:`ScheduleQueue` (Sprint 16.7).

    Orders entries by next-execution tick (insertion order breaks ties) with no
    background worker; each request resolves a fresh queue. Purely additive.
    """
    return scheduler_engine.ScheduleQueue()


ScheduleQueueDep = Annotated[
    scheduler_engine.ScheduleQueue, Depends(get_schedule_queue)
]


def get_workflow_execution_scheduler(
    lifecycle_manager: WorkflowLifecycleManagerDep = None,
) -> scheduler_engine.ExecutionScheduler:
    """Provide the Sprint 16.7 :class:`ExecutionScheduler` (distinct from planning's).

    Composes the frozen Sprint 16.2 :class:`WorkflowLifecycleManager` (constructor
    injection; it instantiates none). It executes due scheduled workflows only
    through the lifecycle manager's ``run`` — never the Workflow Coordinator and
    never a capability. When called outside a FastAPI request the ``= None`` default
    falls back to the fully-wired lifecycle manager. Purely additive.
    """
    return scheduler_engine.ExecutionScheduler(
        lifecycle_manager or get_workflow_lifecycle_manager()
    )


WorkflowExecutionSchedulerDep = Annotated[
    scheduler_engine.ExecutionScheduler,
    Depends(get_workflow_execution_scheduler),
]


def get_scheduler_manager(
    policy: SchedulePolicyDep = None,
    planner: SchedulePlannerDep = None,
    queue: ScheduleQueueDep = None,
    execution_scheduler: WorkflowExecutionSchedulerDep = None,
    persistence: PersistenceEngineDep = None,
    notification: NotificationEngineDep = None,
) -> scheduler_engine.SchedulerManager:
    """Provide the Sprint 16.7 :class:`SchedulerManager`.

    Composes the injected schedule policy, planner, queue, and
    :class:`ExecutionScheduler`, plus the Sprint 16.5 :class:`PersistenceManager` and
    the Sprint 16.4 notification engine (constructor injection; it instantiates none
    of them). It decides *when* workflows execute and delegates the running of due
    schedules to the execution scheduler — it executes no workflow or capability
    itself and uses only deterministic caller-supplied ticks. When called outside a
    FastAPI request the ``= None`` defaults fall back to fresh provider instances.
    Purely additive: a new scheduling seam that changes no existing wiring.
    """
    return scheduler_engine.SchedulerManager(
        policy or get_schedule_policy(),
        planner or get_schedule_planner(),
        queue or get_schedule_queue(),
        execution_scheduler or get_workflow_execution_scheduler(),
        persistence or get_persistence_engine(),
        notification or get_notification_engine(),
    )


SchedulerManagerDep = Annotated[
    scheduler_engine.SchedulerManager, Depends(get_scheduler_manager)
]


def get_failure_classifier() -> recovery_engine.FailureClassifier:
    """Provide the default :class:`FailureClassifier` — keyword-based (16.8).

    Maps a failure reason to a :class:`FailureType` from a configurable keyword
    ruleset (transient/permanent/user-action/system, else unknown). Stateless,
    deterministic. Purely additive.
    """
    return recovery_engine.RuleBasedFailureClassifier()


FailureClassifierDep = Annotated[
    recovery_engine.FailureClassifier, Depends(get_failure_classifier)
]


def get_recovery_policy() -> recovery_engine.RecoveryPolicy:
    """Provide the default recovery policy — :class:`LimitedRetryPolicy` (16.8).

    The default retries a retryable failure up to three attempts, flags a
    permanent/user-action failure for manual handling, and aborts when retries are
    exhausted; the abstraction lets :class:`ImmediateRetryPolicy`/
    :class:`ManualRecoveryPolicy` or a later Sprint 16.x policy swap in with no change
    to the manager. Stateless, deterministic. Purely additive.
    """
    return recovery_engine.LimitedRetryPolicy()


RecoveryPolicyDep = Annotated[
    recovery_engine.RecoveryPolicy, Depends(get_recovery_policy)
]


def get_retry_strategy() -> recovery_engine.RetryStrategy:
    """Provide the default :class:`RetryStrategy` — exponential backoff (16.8).

    Computes next-retry *ticks* deterministically from a caller-supplied tick — no
    timers or wall-clock. Stateless. Purely additive.
    """
    return recovery_engine.RetryStrategy(
        recovery_engine.RetryStrategyType.EXPONENTIAL_BACKOFF
    )


RetryStrategyDep = Annotated[
    recovery_engine.RetryStrategy, Depends(get_retry_strategy)
]


def get_recovery_coordinator(
    lifecycle_manager: WorkflowLifecycleManagerDep = None,
) -> recovery_engine.RecoveryCoordinator:
    """Provide the Sprint 16.8 :class:`RecoveryCoordinator`.

    Composes the frozen Sprint 16.2 :class:`WorkflowLifecycleManager` (constructor
    injection; it instantiates none). It executes recovery only through the lifecycle
    manager's transitions — never the Workflow Coordinator and never a capability.
    When called outside a FastAPI request the ``= None`` default falls back to the
    fully-wired lifecycle manager. Purely additive.
    """
    return recovery_engine.RecoveryCoordinator(
        lifecycle_manager or get_workflow_lifecycle_manager()
    )


RecoveryCoordinatorDep = Annotated[
    recovery_engine.RecoveryCoordinator, Depends(get_recovery_coordinator)
]


def get_recovery_engine(
    policy: RecoveryPolicyDep = None,
    strategy: RetryStrategyDep = None,
    coordinator: RecoveryCoordinatorDep = None,
    classifier: FailureClassifierDep = None,
    persistence: PersistenceEngineDep = None,
    notification: NotificationEngineDep = None,
) -> recovery_engine.RecoveryManager:
    """Provide the Sprint 16.8 :class:`RecoveryManager` engine (distinct from planning's).

    Composes the injected recovery policy, retry strategy, :class:`RecoveryCoordinator`,
    and failure classifier, plus the Sprint 16.5 :class:`PersistenceManager` and the
    Sprint 16.4 notification engine (constructor injection; it instantiates none of
    them). It decides *how* failed workflows recover and delegates every retry/abort
    through the coordinator — it executes no workflow or capability itself and uses
    only deterministic caller-supplied ticks. When called outside a FastAPI request
    the ``= None`` defaults fall back to fresh provider instances. Purely additive: a
    new recovery seam that changes no existing wiring.
    """
    return recovery_engine.RecoveryManager(
        policy or get_recovery_policy(),
        strategy or get_retry_strategy(),
        coordinator or get_recovery_coordinator(),
        classifier or get_failure_classifier(),
        persistence or get_persistence_engine(),
        notification or get_notification_engine(),
    )


RecoveryEngineDep = Annotated[
    recovery_engine.RecoveryManager, Depends(get_recovery_engine)
]


# =====================================================================
# Sprint 16.9 — Agent Coordination Platform
# =====================================================================
def get_agent_registry() -> coordination_platform.AgentRegistry:
    """Provide a fresh :class:`AgentRegistry` — the roster of AI Employees (16.9).

    An in-memory roster that maintains registered agents and decides nothing about
    which agent handles work (the resolver and policy decide). Stateful (holds the
    roster); a fresh instance per call. Purely additive.
    """
    return coordination_platform.AgentRegistry()


AgentRegistryDep = Annotated[
    coordination_platform.AgentRegistry, Depends(get_agent_registry)
]


def get_agent_resolver() -> coordination_platform.AgentResolver:
    """Provide the default :class:`AgentResolver` — availability/role/capability (16.9).

    Filters candidate agents by the configured criteria (available, role match, all
    required capabilities) and ranks them by priority; the flags let a caller relax
    any criterion with no change to the coordinator. Stateless, deterministic.
    Purely additive.
    """
    return coordination_platform.AgentResolver()


AgentResolverDep = Annotated[
    coordination_platform.AgentResolver, Depends(get_agent_resolver)
]


def get_coordination_policy() -> coordination_platform.CoordinationPolicy:
    """Provide the default coordination policy — :class:`SingleAgentPolicy` (16.9).

    The default assigns a task to the single most suitable agent; the abstraction
    lets :class:`CollaborativePolicy`/:class:`PriorityPolicy` or a later policy swap
    in with no change to the coordinator. Stateless, deterministic. Purely additive.
    """
    return coordination_platform.SingleAgentPolicy()


CoordinationPolicyDep = Annotated[
    coordination_platform.CoordinationPolicy, Depends(get_coordination_policy)
]


def get_task_delegator(
    ai_employee: AIEmployeeDep = None,
) -> coordination_platform.TaskDelegator:
    """Provide the Sprint 16.9 :class:`TaskDelegator`.

    Composes the frozen Sprint 16.1 :class:`AIEmployee` (constructor injection; it
    instantiates none). It assigns work by delegating the running to the
    :class:`AIEmployee` — never the Workflow Coordinator and never a capability. When
    called outside a FastAPI request the ``= None`` default falls back to the
    fully-wired :class:`AIEmployee`. Purely additive.
    """
    return coordination_platform.TaskDelegator(
        ai_employee or get_ai_employee()
    )


TaskDelegatorDep = Annotated[
    coordination_platform.TaskDelegator, Depends(get_task_delegator)
]


def get_collaboration_context() -> coordination_platform.CollaborationContext:
    """Provide a fresh :class:`CollaborationContext` — the collaboration ledger (16.9).

    An in-memory ledger of participating agents, delegated tasks, and their
    ownership; it decides nothing and runs nothing. Stateful (holds the ledger); a
    fresh instance per call. Purely additive.
    """
    return coordination_platform.CollaborationContext()


CollaborationContextDep = Annotated[
    coordination_platform.CollaborationContext,
    Depends(get_collaboration_context),
]


def get_agent_coordinator(
    registry: AgentRegistryDep = None,
    resolver: AgentResolverDep = None,
    policy: CoordinationPolicyDep = None,
    delegator: TaskDelegatorDep = None,
    collaboration: CollaborationContextDep = None,
    notification: NotificationEngineDep = None,
) -> coordination_platform.AgentCoordinator:
    """Provide the Sprint 16.9 :class:`AgentCoordinator`.

    Composes the injected :class:`AgentRegistry`, :class:`AgentResolver`,
    :class:`CoordinationPolicy`, :class:`TaskDelegator`, and
    :class:`CollaborationContext`, plus the Sprint 16.4 notification engine
    (constructor injection; it instantiates none of them). It coordinates *which*
    agent handles *which* work and delegates every run through the delegator — it
    executes no workflow or capability itself and does no networking, RPC, or
    messaging. When called outside a FastAPI request the ``= None`` defaults fall
    back to fresh provider instances. Purely additive: a new coordination seam that
    changes no existing wiring.
    """
    return coordination_platform.AgentCoordinator(
        registry or get_agent_registry(),
        resolver or get_agent_resolver(),
        policy or get_coordination_policy(),
        delegator or get_task_delegator(),
        collaboration or get_collaboration_context(),
        notification or get_notification_engine(),
    )


AgentCoordinatorDep = Annotated[
    coordination_platform.AgentCoordinator, Depends(get_agent_coordinator)
]


# =====================================================================
# Sprint 16.10 — AI Employee Service Layer
# =====================================================================
def get_service_session_manager() -> ai_employee_service.SessionManager:
    """Provide a fresh :class:`SessionManager` — the service session ledger (16.10).

    An in-memory ledger of AI Employee service sessions; it holds no execution state
    and runs nothing. Stateful (holds the ledger); a fresh instance per call. Purely
    additive.
    """
    return ai_employee_service.SessionManager()


ServiceSessionManagerDep = Annotated[
    ai_employee_service.SessionManager, Depends(get_service_session_manager)
]


def get_request_validator() -> ai_employee_service.RequestValidator:
    """Provide the stateless :class:`RequestValidator` (16.10).

    Validates incoming :class:`TaskSubmissionRequest`\\ s and raises deterministic
    validation errors. Stateless. Purely additive.
    """
    return ai_employee_service.RequestValidator()


RequestValidatorDep = Annotated[
    ai_employee_service.RequestValidator, Depends(get_request_validator)
]


def get_response_builder() -> ai_employee_service.ResponseBuilder:
    """Provide the stateless :class:`ResponseBuilder` (16.10).

    Builds the service's stable, provider-independent response DTOs. Stateless.
    Purely additive.
    """
    return ai_employee_service.ResponseBuilder()


ResponseBuilderDep = Annotated[
    ai_employee_service.ResponseBuilder, Depends(get_response_builder)
]


def get_idempotency_manager() -> ai_employee_service.IdempotencyManager:
    """Provide a fresh :class:`IdempotencyManager` — the dedup ledger (16.10).

    An in-memory ledger that deduplicates submissions by idempotency key; it stores
    records and computes digests only. Stateful (holds the ledger); a fresh instance
    per call. Purely additive.
    """
    return ai_employee_service.IdempotencyManager()


IdempotencyManagerDep = Annotated[
    ai_employee_service.IdempotencyManager, Depends(get_idempotency_manager)
]


def get_health_manager() -> ai_employee_service.HealthManager:
    """Provide the :class:`HealthManager` over the platform's wired subsystems (16.10).

    Reports provider-independent health/readiness for Planning, Runtime, AIEmployee,
    Memory, Scheduler, Recovery, and Persistence. Each subsystem is reported available
    because it has a wired composition-root provider — the manager holds only these
    plain availability flags, never a provider/SDK object. Stateless, deterministic.
    Purely additive.
    """
    return ai_employee_service.HealthManager(
        {name: True for name in ai_employee_service.HEALTH_COMPONENTS}
    )


HealthManagerDep = Annotated[
    ai_employee_service.HealthManager, Depends(get_health_manager)
]


def get_error_mapper() -> ai_employee_service.ErrorMapper:
    """Provide the stateless :class:`ErrorMapper` (16.10).

    Converts any internal exception into a stable, provider-independent
    :class:`ServiceError`; no raw exception crosses the service boundary. Stateless.
    Purely additive.
    """
    return ai_employee_service.ErrorMapper()


ErrorMapperDep = Annotated[
    ai_employee_service.ErrorMapper, Depends(get_error_mapper)
]


def get_ai_employee_service(
    ai_employee: AIEmployeeDep = None,
    session_manager: ServiceSessionManagerDep = None,
    validator: RequestValidatorDep = None,
    response_builder: ResponseBuilderDep = None,
    idempotency_manager: IdempotencyManagerDep = None,
    health_manager: HealthManagerDep = None,
    error_mapper: ErrorMapperDep = None,
) -> ai_employee_service.AIEmployeeService:
    """Provide the Sprint 16.10 :class:`AIEmployeeService` — the public entry point.

    Composes the frozen Sprint 16.1 :class:`AIEmployee` plus the injected
    :class:`SessionManager`, :class:`RequestValidator`, :class:`ResponseBuilder`,
    :class:`IdempotencyManager`, :class:`HealthManager`, and :class:`ErrorMapper`
    (constructor injection; it instantiates none of them). It coordinates external
    task submission/control and always delegates the running to the
    :class:`AIEmployee` — it executes no workflow or capability itself, never calls
    the Workflow Coordinator, and never surfaces a raw exception. When called outside
    a FastAPI request the ``= None`` defaults fall back to fresh provider instances.
    Purely additive: a new public service seam that changes no existing wiring.
    """
    return ai_employee_service.AIEmployeeService(
        ai_employee or get_ai_employee(),
        session_manager or get_service_session_manager(),
        validator or get_request_validator(),
        response_builder or get_response_builder(),
        idempotency_manager or get_idempotency_manager(),
        health_manager or get_health_manager(),
        error_mapper or get_error_mapper(),
    )


AIEmployeeServiceDep = Annotated[
    ai_employee_service.AIEmployeeService, Depends(get_ai_employee_service)
]


# =====================================================================
# Sprint 16.11 — Enterprise Operations Layer
# =====================================================================
def get_authorization_manager() -> (
    enterprise_operations.AuthorizationManager
):
    """Provide the default local :class:`AuthorizationManager` (16.11).

    A deterministic, local :class:`LocalAuthorizationManager` whose default policy
    binds the ``system`` principal to an ``admin`` role holding the ``"*"`` (all)
    permission; other principals are denied unmapped actions. No authentication, no
    OAuth, no identity provider. Stateless, deterministic. Purely additive.
    """
    return enterprise_operations.LocalAuthorizationManager(
        role_bindings={"system": {"admin"}},
        role_permissions={"admin": {"*"}},
    )


AuthorizationManagerDep = Annotated[
    enterprise_operations.AuthorizationManager,
    Depends(get_authorization_manager),
]


def get_audit_manager() -> enterprise_operations.AuditManager:
    """Provide a fresh :class:`AuditManager` — the append-only audit ledger (16.11).

    An in-memory, append-only ledger of immutable audit records; it never mutates a
    record and runs nothing. Stateful (holds the ledger); a fresh instance per call.
    Purely additive.
    """
    return enterprise_operations.AuditManager()


AuditManagerDep = Annotated[
    enterprise_operations.AuditManager, Depends(get_audit_manager)
]


def get_configuration_manager() -> (
    enterprise_operations.ConfigurationManager
):
    """Provide the default :class:`ConfigurationManager` (16.11).

    Validates the platform's operational configuration deterministically over a small
    default set of settings and required keys. Stateless beyond its immutable config;
    it runs nothing. Purely additive.
    """
    return enterprise_operations.ConfigurationManager(
        defaults={
            "environment": "local",
            "service_name": "ai-employee",
            "max_active_sessions": 100,
        },
        required_keys=["environment", "service_name"],
    )


ConfigurationManagerDep = Annotated[
    enterprise_operations.ConfigurationManager,
    Depends(get_configuration_manager),
]


def get_observability_manager(
    service: AIEmployeeServiceDep = None,
    health_manager: HealthManagerDep = None,
    audit_manager: AuditManagerDep = None,
) -> enterprise_operations.ObservabilityManager:
    """Provide the Sprint 16.11 :class:`ObservabilityManager`.

    Composes the frozen Sprint 16.10 :class:`AIEmployeeService` and
    :class:`HealthManager` and the Sprint 16.11 :class:`AuditManager` (constructor
    injection; it instantiates none). It collects deterministic telemetry by reading
    their public surfaces only — it connects to no external telemetry system. When
    called outside a FastAPI request the ``= None`` defaults fall back to fresh
    provider instances. Purely additive.
    """
    return enterprise_operations.ObservabilityManager(
        service or get_ai_employee_service(),
        health_manager or get_health_manager(),
        audit_manager or get_audit_manager(),
    )


ObservabilityManagerDep = Annotated[
    enterprise_operations.ObservabilityManager,
    Depends(get_observability_manager),
]


def get_deployment_validator(
    configuration_manager: ConfigurationManagerDep = None,
    health_manager: HealthManagerDep = None,
) -> enterprise_operations.DeploymentValidator:
    """Provide the Sprint 16.11 :class:`DeploymentValidator`.

    Composes the injected :class:`ConfigurationManager` and the frozen Sprint 16.10
    :class:`HealthManager` (constructor injection; it instantiates none). It validates
    deployment readiness by reading configuration and health — it deploys and starts
    nothing. When called outside a FastAPI request the ``= None`` defaults fall back to
    fresh provider instances. Purely additive.
    """
    return enterprise_operations.DeploymentValidator(
        configuration_manager or get_configuration_manager(),
        health_manager or get_health_manager(),
    )


DeploymentValidatorDep = Annotated[
    enterprise_operations.DeploymentValidator,
    Depends(get_deployment_validator),
]


def get_diagnostics_manager(
    observability_manager: ObservabilityManagerDep = None,
    deployment_validator: DeploymentValidatorDep = None,
) -> enterprise_operations.DiagnosticsManager:
    """Provide the Sprint 16.11 :class:`DiagnosticsManager`.

    Composes the injected :class:`ObservabilityManager` and
    :class:`DeploymentValidator` (constructor injection; it instantiates none). It
    aggregates diagnostics by reading them only — it connects to no external
    monitoring. When called outside a FastAPI request the ``= None`` defaults fall back
    to fresh provider instances. Purely additive.
    """
    return enterprise_operations.DiagnosticsManager(
        observability_manager or get_observability_manager(),
        deployment_validator or get_deployment_validator(),
    )


DiagnosticsManagerDep = Annotated[
    enterprise_operations.DiagnosticsManager,
    Depends(get_diagnostics_manager),
]


def get_enterprise_operations_manager(
    authorization: AuthorizationManagerDep = None,
    audit: AuditManagerDep = None,
    observability: ObservabilityManagerDep = None,
    configuration: ConfigurationManagerDep = None,
    deployment: DeploymentValidatorDep = None,
    diagnostics: DiagnosticsManagerDep = None,
    service: AIEmployeeServiceDep = None,
    health_manager: HealthManagerDep = None,
) -> enterprise_operations.EnterpriseOperationsManager:
    """Provide the Sprint 16.11 :class:`EnterpriseOperationsManager` — the ops entry point.

    Composes the injected authorization, audit, observability, configuration,
    deployment, and diagnostics managers over the frozen Sprint 16.10
    :class:`AIEmployeeService` (constructor injection; it instantiates none). To keep
    telemetry and audit consistent, when building the defaults it threads a single
    shared :class:`AIEmployeeService`, :class:`HealthManager`, and
    :class:`AuditManager` through the observability, deployment, and diagnostics
    seams. It adds operational capabilities only — it executes no workflow or
    capability, never calls the Workflow Coordinator, and delegates every business
    request to the service. When called outside a FastAPI request the ``= None``
    defaults fall back to these shared instances. Purely additive: a new operations
    seam that changes no existing wiring.
    """
    service = service or get_ai_employee_service()
    health_manager = health_manager or get_health_manager()
    audit = audit or get_audit_manager()
    authorization = authorization or get_authorization_manager()
    configuration = configuration or get_configuration_manager()
    observability = observability or get_observability_manager(
        service, health_manager, audit
    )
    deployment = deployment or get_deployment_validator(
        configuration, health_manager
    )
    diagnostics = diagnostics or get_diagnostics_manager(
        observability, deployment
    )
    return enterprise_operations.EnterpriseOperationsManager(
        authorization,
        audit,
        observability,
        configuration,
        deployment,
        diagnostics,
        service,
    )


EnterpriseOperationsManagerDep = Annotated[
    enterprise_operations.EnterpriseOperationsManager,
    Depends(get_enterprise_operations_manager),
]


# =====================================================================
# Sprint 16.12 — Experience Intelligence Platform
# =====================================================================
def get_feedback_manager() -> experience_intelligence.FeedbackManager:
    """Provide a fresh :class:`FeedbackManager` — the append-only feedback ledger (16.12).

    An in-memory, append-only ledger of immutable feedback records; it never mutates a
    record and runs nothing. Stateful (holds the ledger); a fresh instance per call.
    Purely additive.
    """
    return experience_intelligence.FeedbackManager()


FeedbackManagerDep = Annotated[
    experience_intelligence.FeedbackManager, Depends(get_feedback_manager)
]


def get_experience_analyzer(
    service: AIEmployeeServiceDep = None,
) -> experience_intelligence.ExperienceAnalyzer:
    """Provide the Sprint 16.12 :class:`ExperienceAnalyzer`.

    Composes the frozen Sprint 16.10 :class:`AIEmployeeService` (constructor injection;
    it instantiates none). It measures task experience by reading the service's task
    list only — it observes, never executes. When called outside a FastAPI request the
    ``= None`` default falls back to a fresh service instance. Purely additive.
    """
    return experience_intelligence.ExperienceAnalyzer(
        service or get_ai_employee_service()
    )


ExperienceAnalyzerDep = Annotated[
    experience_intelligence.ExperienceAnalyzer,
    Depends(get_experience_analyzer),
]


def get_behavior_analyzer(
    service: AIEmployeeServiceDep = None,
) -> experience_intelligence.BehaviorAnalyzer:
    """Provide the Sprint 16.12 :class:`BehaviorAnalyzer`.

    Composes the frozen Sprint 16.10 :class:`AIEmployeeService` (constructor injection;
    it instantiates none). It measures usage behaviour by reading the service's task
    and session state only — it observes, never executes. When called outside a FastAPI
    request the ``= None`` default falls back to a fresh service instance. Purely
    additive.
    """
    return experience_intelligence.BehaviorAnalyzer(
        service or get_ai_employee_service()
    )


BehaviorAnalyzerDep = Annotated[
    experience_intelligence.BehaviorAnalyzer, Depends(get_behavior_analyzer)
]


def get_quality_evaluator(
    service: AIEmployeeServiceDep = None,
) -> experience_intelligence.QualityEvaluator:
    """Provide the Sprint 16.12 :class:`QualityEvaluator`.

    Composes the frozen Sprint 16.10 :class:`AIEmployeeService` (constructor injection;
    it instantiates none). It evaluates task quality with a fixed rule-based score by
    reading observed task state only — no AI, no LLM evaluation. When called outside a
    FastAPI request the ``= None`` default falls back to a fresh service instance.
    Purely additive.
    """
    return experience_intelligence.QualityEvaluator(
        service or get_ai_employee_service()
    )


QualityEvaluatorDep = Annotated[
    experience_intelligence.QualityEvaluator, Depends(get_quality_evaluator)
]


def get_friction_detector(
    service: AIEmployeeServiceDep = None,
) -> experience_intelligence.FrictionDetector:
    """Provide the Sprint 16.12 :class:`FrictionDetector`.

    Composes the frozen Sprint 16.10 :class:`AIEmployeeService` (constructor injection;
    it instantiates none) with deterministic default thresholds. It detects workflow
    friction by reading observed task state only — it observes, never executes. When
    called outside a FastAPI request the ``= None`` default falls back to a fresh
    service instance. Purely additive.
    """
    return experience_intelligence.FrictionDetector(
        service or get_ai_employee_service()
    )


FrictionDetectorDep = Annotated[
    experience_intelligence.FrictionDetector, Depends(get_friction_detector)
]


def get_recommendation_engine() -> (
    experience_intelligence.RecommendationEngine
):
    """Provide the stateless :class:`RecommendationEngine` (16.12).

    Generates deterministic, rule-based improvement recommendations from the computed
    metrics — there is NO AI generation. It holds no collaborator, session, or state
    beyond its immutable thresholds and runs nothing. Purely additive.
    """
    return experience_intelligence.RecommendationEngine()


RecommendationEngineDep = Annotated[
    experience_intelligence.RecommendationEngine,
    Depends(get_recommendation_engine),
]


def get_improvement_reporter() -> (
    experience_intelligence.ImprovementReporter
):
    """Provide the stateless :class:`ImprovementReporter` (16.12).

    Formats already-computed metrics, friction, quality, and recommendations into
    immutable reports and the platform summary. It is a pure formatter — it holds no
    state and runs nothing. Purely additive.
    """
    return experience_intelligence.ImprovementReporter()


ImprovementReporterDep = Annotated[
    experience_intelligence.ImprovementReporter,
    Depends(get_improvement_reporter),
]


def get_experience_intelligence_manager(
    feedback: FeedbackManagerDep = None,
    experience_analyzer: ExperienceAnalyzerDep = None,
    behavior_analyzer: BehaviorAnalyzerDep = None,
    quality_evaluator: QualityEvaluatorDep = None,
    friction_detector: FrictionDetectorDep = None,
    recommendation_engine: RecommendationEngineDep = None,
    reporter: ImprovementReporterDep = None,
    service: AIEmployeeServiceDep = None,
) -> experience_intelligence.ExperienceIntelligenceManager:
    """Provide the Sprint 16.12 :class:`ExperienceIntelligenceManager` — the entry point.

    Composes the injected feedback, experience/behaviour analyzers, quality evaluator,
    friction detector, recommendation engine, and reporter over the frozen Sprint 16.10
    :class:`AIEmployeeService` (constructor injection; it instantiates none). So every
    analyzer observes the same platform state, when building the defaults it threads a
    single shared :class:`AIEmployeeService` through the analyzer/evaluator/detector
    seams. It observes only — it executes no workflow or capability, never calls the
    Workflow Coordinator, and delegates every business request to the service. When
    called outside a FastAPI request the ``= None`` defaults fall back to these shared
    instances. Purely additive: a new observational seam that changes no existing
    wiring.
    """
    service = service or get_ai_employee_service()
    feedback = feedback or get_feedback_manager()
    experience_analyzer = experience_analyzer or get_experience_analyzer(
        service
    )
    behavior_analyzer = behavior_analyzer or get_behavior_analyzer(service)
    quality_evaluator = quality_evaluator or get_quality_evaluator(service)
    friction_detector = friction_detector or get_friction_detector(service)
    recommendation_engine = (
        recommendation_engine or get_recommendation_engine()
    )
    reporter = reporter or get_improvement_reporter()
    return experience_intelligence.ExperienceIntelligenceManager(
        feedback,
        experience_analyzer,
        behavior_analyzer,
        quality_evaluator,
        friction_detector,
        recommendation_engine,
        reporter,
        service,
    )


ExperienceIntelligenceManagerDep = Annotated[
    experience_intelligence.ExperienceIntelligenceManager,
    Depends(get_experience_intelligence_manager),
]


# =====================================================================
# Sprint 16.13 — Production Validation Platform
# =====================================================================
def get_system_validator(
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.SystemValidator:
    """Provide the Sprint 16.13 :class:`SystemValidator`.

    Composes the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). It validates each subsystem by reading the
    operations status surface — it observes, never executes. When called outside a
    FastAPI request the ``= None`` default falls back to a fresh operations manager.
    Purely additive.
    """
    return production_validation.SystemValidator(
        operations or get_enterprise_operations_manager()
    )


SystemValidatorDep = Annotated[
    production_validation.SystemValidator, Depends(get_system_validator)
]


def get_integration_validator(
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.IntegrationValidator:
    """Provide the Sprint 16.13 :class:`IntegrationValidator`.

    Composes the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). It validates the wiring between subsystems by
    reading the DI graph and health surface — it exercises no interaction. When called
    outside a FastAPI request the ``= None`` default falls back to a fresh operations
    manager. Purely additive.
    """
    return production_validation.IntegrationValidator(
        operations or get_enterprise_operations_manager()
    )


IntegrationValidatorDep = Annotated[
    production_validation.IntegrationValidator,
    Depends(get_integration_validator),
]


def get_performance_validator(
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.PerformanceValidator:
    """Provide the Sprint 16.13 :class:`PerformanceValidator`.

    Composes the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). It measures deterministic counters by reading the
    observability surface — no timer, benchmark, or load generator. When called outside
    a FastAPI request the ``= None`` default falls back to a fresh operations manager.
    Purely additive.
    """
    return production_validation.PerformanceValidator(
        operations or get_enterprise_operations_manager()
    )


PerformanceValidatorDep = Annotated[
    production_validation.PerformanceValidator,
    Depends(get_performance_validator),
]


def get_reliability_validator(
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.ReliabilityValidator:
    """Provide the Sprint 16.13 :class:`ReliabilityValidator`.

    Composes the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). It validates reliability through read-only state
    checks — it exercises no recovery. When called outside a FastAPI request the
    ``= None`` default falls back to a fresh operations manager. Purely additive.
    """
    return production_validation.ReliabilityValidator(
        operations or get_enterprise_operations_manager()
    )


ReliabilityValidatorDep = Annotated[
    production_validation.ReliabilityValidator,
    Depends(get_reliability_validator),
]


def get_security_validator() -> production_validation.SecurityValidator:
    """Provide the stateless :class:`SecurityValidator` (16.13).

    Validates boundaries and isolation by statically inspecting the platform packages'
    source and DTO config — it contacts no host and runs no scanner. It holds no
    collaborator or state. Purely additive.
    """
    return production_validation.SecurityValidator()


SecurityValidatorDep = Annotated[
    production_validation.SecurityValidator, Depends(get_security_validator)
]


def get_compatibility_validator(
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.CompatibilityValidator:
    """Provide the Sprint 16.13 :class:`CompatibilityValidator`.

    Composes the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). It validates the DI graph, configuration,
    providers, and module compatibility by reading the wired graph — it constructs no
    graph. When called outside a FastAPI request the ``= None`` default falls back to a
    fresh operations manager. Purely additive.
    """
    return production_validation.CompatibilityValidator(
        operations or get_enterprise_operations_manager()
    )


CompatibilityValidatorDep = Annotated[
    production_validation.CompatibilityValidator,
    Depends(get_compatibility_validator),
]


def get_validation_reporter() -> production_validation.ValidationReporter:
    """Provide the stateless :class:`ValidationReporter` (16.13).

    Formats already-computed validation results and the readiness verdict into immutable
    reports. It is a pure formatter — it holds no state and runs nothing. Purely
    additive.
    """
    return production_validation.ValidationReporter()


ValidationReporterDep = Annotated[
    production_validation.ValidationReporter, Depends(get_validation_reporter)
]


def get_production_validation_manager(
    system: SystemValidatorDep = None,
    integration: IntegrationValidatorDep = None,
    performance: PerformanceValidatorDep = None,
    reliability: ReliabilityValidatorDep = None,
    security: SecurityValidatorDep = None,
    compatibility: CompatibilityValidatorDep = None,
    reporter: ValidationReporterDep = None,
    operations: EnterpriseOperationsManagerDep = None,
) -> production_validation.ProductionValidationManager:
    """Provide the Sprint 16.13 :class:`ProductionValidationManager` — the entry point.

    Composes the injected system, integration, performance, reliability, security, and
    compatibility validators plus the reporter over the frozen Sprint 16.11
    :class:`EnterpriseOperationsManager` (constructor injection; it instantiates none).
    So every validator reads the same platform state, when building the defaults it
    threads a single shared :class:`EnterpriseOperationsManager` through the
    operations-backed validator seams. It validates only — it executes no workflow or
    capability, never calls the Workflow Coordinator, and delegates only to the
    operations manager for the platform's overall state. When called outside a FastAPI
    request the ``= None`` defaults fall back to these shared instances. Purely additive:
    a new validation seam that changes no existing wiring.
    """
    operations = operations or get_enterprise_operations_manager()
    system = system or get_system_validator(operations)
    integration = integration or get_integration_validator(operations)
    performance = performance or get_performance_validator(operations)
    reliability = reliability or get_reliability_validator(operations)
    security = security or get_security_validator()
    compatibility = compatibility or get_compatibility_validator(operations)
    reporter = reporter or get_validation_reporter()
    return production_validation.ProductionValidationManager(
        system,
        integration,
        performance,
        reliability,
        security,
        compatibility,
        reporter,
        operations,
    )


ProductionValidationManagerDep = Annotated[
    production_validation.ProductionValidationManager,
    Depends(get_production_validation_manager),
]


def get_interaction_provider() -> InteractionProvider:
    """Provide the active interaction provider (Sprint 12.1).

    Sprint 12.1 ships only the multimodal interaction framework — no concrete
    interaction provider exists yet — so this composition-root seam is
    intentionally unfulfilled and raises. A later sprint registers a real
    provider here (the one place providers are constructed), with no change
    required in :class:`InteractionService` or its consumers.
    """
    raise NotImplementedError(
        "No interaction provider is implemented yet (Sprint 12.1 ships only the "
        "multimodal interaction framework); a concrete provider is wired here in "
        "a later sprint."
    )


InteractionProviderDep = Annotated[
    InteractionProvider, Depends(get_interaction_provider)
]


def get_interaction_service(
    provider: InteractionProviderDep,
) -> InteractionService:
    """Provide an :class:`InteractionService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service — it is the Sprint 12.1 framework only, a
    new interface into the existing Agent Execution Core that leaves the Runtime,
    Planner, Permission, Registry, and Execution layers untouched.
    """
    return InteractionService(provider)


InteractionServiceDep = Annotated[
    InteractionService, Depends(get_interaction_service)
]


def get_optional_planner_service() -> Optional[PlannerService]:
    """Provide a :class:`PlannerService` if available, else ``None`` (11.5).

    The Sprint 11.4 planner-provider seam is intentionally unfulfilled, so this
    composition-root assembler tolerates the gap: it returns ``None`` until a
    concrete provider exists. The AI orchestrator's runtime ``run`` path never
    uses the planner, so this keeps the runtime DI chain resolvable; the agent
    ``execute_agent_request`` path activates once a provider is wired.
    """
    try:
        provider = get_planner_provider()
    except NotImplementedError:
        return None
    return PlannerService(provider)


OptionalPlannerServiceDep = Annotated[
    Optional[PlannerService], Depends(get_optional_planner_service)
]


def get_optional_permission_service() -> Optional[PermissionService]:
    """Provide a :class:`PermissionService` if available, else ``None`` (11.5).

    Tolerates Sprint 11.3's unfulfilled permission-provider seam so the runtime
    DI chain resolves; returns a real service once a provider is wired.
    """
    try:
        provider = get_permission_provider()
    except NotImplementedError:
        return None
    return PermissionService(provider)


OptionalPermissionServiceDep = Annotated[
    Optional[PermissionService], Depends(get_optional_permission_service)
]


def get_optional_tool_execution_service() -> Optional[ToolExecutionService]:
    """Provide a :class:`ToolExecutionService` if available, else ``None`` (11.5).

    Tolerates Sprint 11.1's unfulfilled tool-provider seam so the runtime DI
    chain resolves; returns a real service once a provider is wired.
    """
    try:
        provider = get_tool_provider()
    except NotImplementedError:
        return None
    return ToolExecutionService(provider)


OptionalToolExecutionServiceDep = Annotated[
    Optional[ToolExecutionService], Depends(get_optional_tool_execution_service)
]


def get_ai_orchestrator_service(
    prompt_builder: RuntimePromptBuilderServiceDep,
    provider_factory: ConversationProviderFactoryDep,
    planner: OptionalPlannerServiceDep,
    permissions: OptionalPermissionServiceDep,
    tool_registry: ToolRegistryDep,
    tool_execution: OptionalToolExecutionServiceDep,
) -> AIOrchestratorService:
    """Provide the AI orchestrator (Sprint 7.3; Sprint 11.5 adds agent core).

    Reuses the Sprint 7.2 runtime prompt builder and the Sprint 6 provider
    factory for the existing ``run`` path. Sprint 11.5 also injects the Sprint
    11.2–11.4 agent-execution collaborators — planner, permission service, tool
    registry, and tool execution service — so the orchestrator can coordinate
    ``execute_agent_request``. The planner/permission/tool-execution services
    are ``None`` until their provider seams are fulfilled (their runtime ``run``
    path is unaffected). All injected; holds no session and instantiates nothing.
    """
    return AIOrchestratorService(
        prompt_builder,
        provider_factory,
        planner=planner,
        permissions=permissions,
        tool_registry=tool_registry,
        tool_execution=tool_execution,
    )


AIOrchestratorServiceDep = Annotated[
    AIOrchestratorService, Depends(get_ai_orchestrator_service)
]


def get_conversation_runtime_service(
    context_engine: AIContextEngineServiceDep,
    prompt_builder: RuntimePromptBuilderServiceDep,
    orchestrator: AIOrchestratorServiceDep,
    memory_persistence: MemoryPersistenceServiceDep,
) -> ConversationRuntimeService:
    """Provide the Sprint 7.4 conversation runtime service (single entry point).

    Reuses the Sprint 7.1 context engine, Sprint 7.2 prompt builder, Sprint 7.3
    orchestrator, and (Sprint 8.2) the Sprint 8.1 memory persistence service —
    all injected; adds only coordination. Holds no session.
    """
    return ConversationRuntimeService(
        context_engine, prompt_builder, orchestrator, memory_persistence
    )


ConversationRuntimeServiceDep = Annotated[
    ConversationRuntimeService, Depends(get_conversation_runtime_service)
]


def get_conversation_generation_service(
    session: SessionDep,
    ai_context: AIContextServiceDep,
    prompt_builder: PromptBuilderServiceDep,
    provider_factory: ConversationProviderFactoryDep,
) -> ConversationGenerationService:
    """Provide a :class:`ConversationGenerationService` bound to the session.

    The AI context, prompt builder, and provider factory are injected through
    DI; the AI context service is built from the same request-scoped session,
    so the whole generation flow shares one transaction.
    """
    return ConversationGenerationService(
        session, ai_context, prompt_builder, provider_factory
    )


def get_interview_question_service(
    session: SessionDep,
) -> InterviewQuestionService:
    """Provide an :class:`InterviewQuestionService` bound to the session."""
    return InterviewQuestionService(session)


def get_interview_answer_service(
    session: SessionDep,
) -> InterviewAnswerService:
    """Provide an :class:`InterviewAnswerService` bound to the session."""
    return InterviewAnswerService(session)


def get_interview_session_service(
    session: SessionDep,
) -> InterviewSessionService:
    """Provide an :class:`InterviewSessionService` bound to the session."""
    return InterviewSessionService(session)


def get_interview_session_question_service(
    session: SessionDep,
) -> InterviewSessionQuestionService:
    """Provide an :class:`InterviewSessionQuestionService` bound to the session."""
    return InterviewSessionQuestionService(session)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    session: SessionDep,
) -> User:
    """Resolve the authenticated user from a Bearer *access* token.

    Raises ``401 Unauthorized`` if the token is invalid, expired, of the wrong
    type, or does not map to an active user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise credentials_exception

    if claims.get("type") != "access":
        raise credentials_exception

    subject = claims.get("sub")
    if not subject:
        raise credentials_exception
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_exception

    user = UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service)]
BlueprintServiceDep = Annotated[BlueprintService, Depends(get_blueprint_service)]
BlueprintGenerationServiceDep = Annotated[
    BlueprintGenerationService, Depends(get_blueprint_generation_service)
]
BlueprintApplyServiceDep = Annotated[
    BlueprintApplyService, Depends(get_blueprint_apply_service)
]
BlueprintVersionServiceDep = Annotated[
    BlueprintVersionService, Depends(get_blueprint_version_service)
]
BlueprintRestoreServiceDep = Annotated[
    BlueprintRestoreService, Depends(get_blueprint_restore_service)
]
ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
MemoryContextServiceDep = Annotated[
    MemoryContextService, Depends(get_memory_context_service)
]
ConversationContextServiceDep = Annotated[
    ConversationContextService, Depends(get_conversation_context_service)
]
ConversationGenerationServiceDep = Annotated[
    ConversationGenerationService,
    Depends(get_conversation_generation_service),
]
InterviewQuestionServiceDep = Annotated[
    InterviewQuestionService, Depends(get_interview_question_service)
]
InterviewAnswerServiceDep = Annotated[
    InterviewAnswerService, Depends(get_interview_answer_service)
]
InterviewSessionServiceDep = Annotated[
    InterviewSessionService, Depends(get_interview_session_service)
]
InterviewSessionQuestionServiceDep = Annotated[
    InterviewSessionQuestionService,
    Depends(get_interview_session_question_service),
]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
