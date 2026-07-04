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
from app.services.interaction import (
    InteractionProvider,
    InteractionService,
)
from app.services.multimodal_ai import (
    MultimodalAIProvider,
    MultimodalAIService,
)
from app.services.multimodal_ai.adapters import MultimodalAIAdapter
from app.services.multimodal_ai.providers import GeminiProvider, ProviderConfig
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


def get_multimodal_ai_provider() -> MultimodalAIProvider:
    """Provide the active multimodal AI provider (Sprint 12.2).

    Sprint 12.2 ships only the multimodal AI provider framework — no concrete
    provider exists yet — so this composition-root seam is intentionally
    unfulfilled and raises. A later sprint registers a real provider here (the
    one place providers are constructed), with no change required in
    :class:`MultimodalAIService` or its consumers.
    """
    raise NotImplementedError(
        "No multimodal AI provider is implemented yet (Sprint 12.2 ships only "
        "the provider framework); a concrete provider is wired here in a later "
        "sprint."
    )


MultimodalAIProviderDep = Annotated[
    MultimodalAIProvider, Depends(get_multimodal_ai_provider)
]


def get_multimodal_ai_service(
    provider: MultimodalAIProviderDep,
) -> MultimodalAIService:
    """Provide a :class:`MultimodalAIService` bound to the active provider.

    The provider is injected from the composition root (constructor injection);
    the service never instantiates a provider itself. Holds no session. Not yet
    consumed by any router or service, and not wired into the Runtime or AI
    Orchestrator — it is the Sprint 12.2 framework only.
    """
    return MultimodalAIService(provider)


MultimodalAIServiceDep = Annotated[
    MultimodalAIService, Depends(get_multimodal_ai_service)
]


def get_multimodal_ai_adapter() -> MultimodalAIAdapter:
    """Provide the active multimodal AI adapter (Sprint 12.3).

    Sprint 12.3 ships only the adapter framework — no concrete adapter exists
    yet — so this composition-root seam is intentionally unfulfilled and raises.
    A later sprint registers a real adapter here (the one place adapters are
    constructed) beneath a concrete provider, with no change required in
    :class:`MultimodalAIAdapter`'s consumers. The adapter is deliberately NOT
    injected into any provider, the Runtime, or the AI Orchestrator in this
    sprint — nothing is wired.
    """
    raise NotImplementedError(
        "No multimodal AI adapter is implemented yet (Sprint 12.3 ships only "
        "the adapter framework); a concrete adapter is wired here in a later "
        "sprint."
    )


MultimodalAIAdapterDep = Annotated[
    MultimodalAIAdapter, Depends(get_multimodal_ai_adapter)
]


def get_provider_config() -> ProviderConfig:
    """Provide the immutable provider-layer configuration (Sprint 12.4).

    The composition root is the single legitimate place a concrete model name is
    chosen; business logic never hardcodes it (the provider reads the model only
    from ``ProviderConfig.default_model``). Not consumed for generation yet — it
    becomes part of the provider architecture for future sprints.
    """
    return ProviderConfig(
        provider_name="gemini",
        default_model="gemini-live-2.5",
    )


ProviderConfigDep = Annotated[ProviderConfig, Depends(get_provider_config)]


def get_gemini_provider(
    adapter: MultimodalAIAdapterDep,
    config: ProviderConfigDep,
) -> GeminiProvider:
    """Provide the first concrete MultimodalAIProvider (Gemini business layer).

    Constructor injection only: the Sprint 12.3 adapter seam and the provider
    config are injected here; the provider never instantiates an adapter itself.
    The adapter seam still raises ``NotImplementedError`` until a later sprint
    supplies a concrete adapter, so this provider is a DI seam only — not yet
    resolvable at runtime, and not wired into the Runtime, AI Orchestrator, or
    any route.
    """
    return GeminiProvider(adapter, config)


GeminiProviderDep = Annotated[GeminiProvider, Depends(get_gemini_provider)]


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
