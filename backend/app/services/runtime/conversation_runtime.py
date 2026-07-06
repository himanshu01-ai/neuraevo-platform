"""Conversation Runtime (Sprint 12.14 — orchestration only).

The single continuous entry point that makes one AI employee feel like ONE
conversation: the user never "switches modes" between text, audio, images,
documents, and actions — the runtime routes each normalized request over the
same live session and returns one aggregated, provider-independent
:class:`RuntimeResponse`.

The runtime ONLY orchestrates. It owns:

* conversation state (which live session serves which conversation),
* session coordination (create once, reuse, never reconnect unnecessarily),
* deterministic request classification (rule-based ``_RequestClassifier``),
* routing to the reused Sprint 12 communication stack,
* memory coordination (optional context request + turn storage — both
  delegated to the reused Sprint 8/9 memory services),
* response aggregation (``_ResponseAssembler``).

It owns NOTHING else: no business logic, no AI/LLM logic, no provider logic,
no tool logic, no memory implementation, no SDK import, no retries, no
caching, no persistence redesign. Every capability below it is reused
unchanged:

    Session lifecycle   -> Sprint 12.6 :class:`SessionService` (frozen SPI)
    Text/Audio/Visual/
    Document transport  -> Sprint 12.9–12.12 live messaging (via the
                           provider-independent :class:`LiveMessagingPort`)
    Action execution    -> Sprint 12.13 ``execute_action`` which forwards into
                           the Sprint 11 pipeline (planner -> registry ->
                           permission -> tool execution); the runtime never
                           bypasses any stage and never executes a tool
    Memory              -> Sprint 9.1 :class:`MemoryRetrievalService` and
                           Sprint 8.1 :class:`MemoryPersistenceService`

Distinct from the Sprint 7.4 :class:`ConversationRuntimeService` (the
request/response text-generation pipeline), which remains unchanged.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from app.models.user import User
from app.schemas.ai_response import AIResponse, AIResponseMetadata
from app.services.memory import MemoryPersistenceService, MemoryRetrievalService
from app.services.runtime.models import (
    RuntimeRequest,
    RuntimeRequestType,
    RuntimeResponse,
)
from app.services.session import (
    ConversationSession,
    SessionResult,
    SessionService,
)
from app.services.session.providers.gemini_live_provider import (
    ActionRequest,
    ActionResult,
    DocumentInput,
    VisualInput,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class LiveMessagingPort(Protocol):
    """Provider-independent structural view of the live messaging surface.

    Describes ONLY the Sprint 12.9–12.13 send/receive/action operations the
    runtime coordinates — every parameter and return type is a plain value or
    a provider-independent DTO (never an SDK object). The concrete Gemini Live
    session provider satisfies this protocol structurally; the runtime never
    names, imports, or constructs a concrete provider, so provider replacement
    requires no runtime change. ``name`` is the neutral provider identifier
    (already part of the frozen Session SPI) used purely for provenance.
    """

    name: str

    def send_message(
        self, session_id: uuid.UUID, message: str
    ) -> SessionResult: ...

    def receive_response(self, session_id: uuid.UUID) -> str: ...

    def send_audio_chunk(
        self, session_id: uuid.UUID, pcm_chunk: bytes
    ) -> SessionResult: ...

    def receive_audio_chunk(self, session_id: uuid.UUID) -> bytes: ...

    def send_visual_input(
        self, session_id: uuid.UUID, visual_input: VisualInput
    ) -> SessionResult: ...

    def receive_visual_response(self, session_id: uuid.UUID) -> str: ...

    def send_document(
        self, session_id: uuid.UUID, document_input: DocumentInput
    ) -> SessionResult: ...

    def receive_document_response(self, session_id: uuid.UUID) -> str: ...

    def execute_action(
        self, session_id: uuid.UUID, action_request: ActionRequest
    ) -> ActionResult: ...


@dataclass(frozen=True)
class RuntimeContext:
    """Immutable per-turn coordination context (runtime-private value object).

    Bundles the facts the runtime establishes while coordinating ONE turn — the
    normalized ``request``, the optional ``owner``, the deterministic
    ``request_type``, the reused-or-created ``session``, whether that session
    was ``session_reused``, and the ``memory_context_messages`` count — into a
    single immutable value. It exists purely to replace the long parameter
    lists that were threaded between :meth:`ConversationRuntime.execute` and its
    private helpers (assembly and turn storage); it carries no behavior, adds no
    state to the runtime instance, and never crosses the runtime boundary — the
    boundary result is always the provider-independent :class:`RuntimeResponse`.
    ``frozen=True`` makes it immutable, so a turn's established context cannot be
    mutated once built. This is a maintainability construct only: routing,
    classification, memory coordination, and session coordination are unchanged.
    """

    request: RuntimeRequest
    owner: Optional[User]
    request_type: RuntimeRequestType
    session: ConversationSession
    session_reused: bool
    memory_context_messages: Optional[int] = None


class _RequestClassifier:
    """Runtime-PRIVATE, rule-based request classifier (no AI, no LLM).

    Receives one normalized :class:`RuntimeRequest` and classifies it into
    exactly one :class:`RuntimeRequestType` using pure structural rules:

    * ``action`` set                          -> ``ACTION``
    * ``document`` set                        -> ``DOCUMENT``
    * ``visual`` set                          -> ``VISUAL``
    * ``audio`` set (non-empty bytes)         -> ``AUDIO``
    * ``text`` set (non-whitespace string)    -> ``TEXT``

    Exactly ONE payload must be present: zero payloads and ambiguous requests
    (more than one payload) both classify as ``UNKNOWN`` — the classifier never
    guesses. Whitespace-only text and empty audio count as absent. The same
    input always yields the same output, keeping runtime routing deterministic.
    """

    def classify(self, request: RuntimeRequest) -> RuntimeRequestType:
        """Return the single deterministic type for ``request``."""
        candidates = []
        if request.action is not None:
            candidates.append(RuntimeRequestType.ACTION)
        if request.document is not None:
            candidates.append(RuntimeRequestType.DOCUMENT)
        if request.visual is not None:
            candidates.append(RuntimeRequestType.VISUAL)
        if (
            isinstance(request.audio, (bytes, bytearray))
            and len(request.audio) > 0
        ):
            candidates.append(RuntimeRequestType.AUDIO)
        if isinstance(request.text, str) and request.text.strip():
            candidates.append(RuntimeRequestType.TEXT)
        if len(candidates) != 1:
            return RuntimeRequestType.UNKNOWN
        return candidates[0]


class _ResponseAssembler:
    """Runtime-PRIVATE assembler building the one aggregated RuntimeResponse.

    Collects the plain outputs the runtime coordinated — the routed modality
    output (text or audio), the Sprint 11 action outcome, the session identity,
    and the memory-coordination facts — and builds exactly one immutable,
    provider-independent :class:`RuntimeResponse`. It never receives, stores,
    or exposes a provider DTO wrapper or SDK object, and it performs no
    interpretation of the collected outputs.
    """

    def assemble(
        self,
        context: RuntimeContext,
        *,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        action_result: Optional[ActionResult] = None,
    ) -> RuntimeResponse:
        """Build the single immutable response for one coordinated turn.

        The turn's established facts (request type, session, ownership, memory
        count, reuse) are read from the immutable :class:`RuntimeContext`; only
        the routed modality outputs are passed alongside it.
        """
        metadata: Dict[str, Any] = {"session_reused": context.session_reused}
        if context.memory_context_messages is not None:
            metadata["memory_context_messages"] = context.memory_context_messages
        return RuntimeResponse(
            request_type=context.request_type,
            session_id=context.session.session_id,
            conversation_id=context.request.conversation_id,
            employee_id=context.request.employee_id,
            text=text,
            audio=audio,
            action_result=action_result,
            metadata=metadata,
        )


class ConversationRuntime:
    """Orchestrates one continuous multimodal conversation over one session.

    Collaborators are injected (constructor injection, composition root only):
    the Sprint 12.6 :class:`SessionService` for lifecycle, a
    :class:`LiveMessagingPort` for the Sprint 12.9–12.13 message/action
    surface (both wired to the SAME provider instance at the composition
    root), and the optional Sprint 9.1/8.1 memory services (``None`` disables
    memory coordination without affecting routing). The runtime instantiates
    no service, repository, provider, or SDK object — its only private helpers
    are the deterministic ``_RequestClassifier`` and the ``_ResponseAssembler``.
    """

    def __init__(
        self,
        session_service: SessionService,
        live_messaging: LiveMessagingPort,
        memory_retrieval: Optional[MemoryRetrievalService] = None,
        memory_persistence: Optional[MemoryPersistenceService] = None,
    ) -> None:
        self.session_service = session_service
        self.live_messaging = live_messaging
        self.memory_retrieval = memory_retrieval
        self.memory_persistence = memory_persistence
        self._classifier = _RequestClassifier()
        self._assembler = _ResponseAssembler()
        # Conversation state: (conversation_id, employee_id) -> session_id.
        # Pure coordination bookkeeping — the sessions themselves live behind
        # the Session SPI; nothing here is a cache of provider data.
        self._active_sessions: Dict[
            Tuple[uuid.UUID, uuid.UUID], uuid.UUID
        ] = {}

    def execute(
        self, request: RuntimeRequest, owner: Optional[User] = None
    ) -> RuntimeResponse:
        """Coordinate one turn: classify -> session -> memory -> route -> assemble.

        Classifies the request (rule-based; ``UNKNOWN`` raises ``ValueError``
        before any side effect), ensures exactly one live session for the
        conversation (created once, reused after), optionally requests memory
        context, routes the request to the reused communication stack, and —
        for text turns with an ``owner`` — stores the completed turn via the
        reused memory persistence service. Returns the single aggregated
        :class:`RuntimeResponse`. Exceptions from every coordinated service
        propagate unchanged; nothing is retried, cached, or swallowed here.
        """
        request_type = self._classifier.classify(request)
        if request_type is RuntimeRequestType.UNKNOWN:
            raise ValueError(
                "RuntimeRequest is not classifiable: exactly one of text, "
                "audio, visual, document, or action must be provided."
            )

        session, session_reused = self._ensure_session(request)
        context = RuntimeContext(
            request=request,
            owner=owner,
            request_type=request_type,
            session=session,
            session_reused=session_reused,
            memory_context_messages=self._load_memory_context(owner, request),
        )

        text_out: Optional[str] = None
        audio_out: Optional[bytes] = None
        action_out: Optional[ActionResult] = None
        session_id = session.session_id

        if request_type is RuntimeRequestType.TEXT:
            self.live_messaging.send_message(session_id, request.text)
            text_out = self.live_messaging.receive_response(session_id)
        elif request_type is RuntimeRequestType.AUDIO:
            self.live_messaging.send_audio_chunk(session_id, request.audio)
            audio_out = self.live_messaging.receive_audio_chunk(session_id)
        elif request_type is RuntimeRequestType.VISUAL:
            self.live_messaging.send_visual_input(session_id, request.visual)
            text_out = self.live_messaging.receive_visual_response(session_id)
        elif request_type is RuntimeRequestType.DOCUMENT:
            self.live_messaging.send_document(session_id, request.document)
            text_out = self.live_messaging.receive_document_response(
                session_id
            )
        else:  # RuntimeRequestType.ACTION
            # Forwarded through Sprint 12.13's translation layer into the
            # Sprint 11 pipeline (planner -> registry -> permission -> tool
            # execution). The runtime never bypasses a stage and never
            # executes, plans, resolves, or permissions a tool itself.
            action_out = self.live_messaging.execute_action(
                session_id, request.action
            )

        self._store_turn(context, text_out)

        logger.info(
            "Conversation runtime routed %s request for conversation %s "
            "employee %s over session %s (reused=%s)",
            request_type.value,
            request.conversation_id,
            request.employee_id,
            session_id,
            session_reused,
        )
        return self._assembler.assemble(
            context,
            text=text_out,
            audio=audio_out,
            action_result=action_out,
        )

    def close_conversation(self, request: RuntimeRequest) -> bool:
        """Close the conversation's live session (if any) via the Session SPI.

        Coordination only: looks up the tracked session for the conversation,
        delegates the close to the reused :class:`SessionService`, and drops
        the bookkeeping entry. Returns whether a session was closed.
        """
        key = (request.conversation_id, request.employee_id)
        session_id = self._active_sessions.pop(key, None)
        if session_id is None:
            return False
        result = self.session_service.close_session(session_id)
        return bool(result.success)

    # ------------------------------------------------------------------
    # Internals — session coordination (runtime-private)
    # ------------------------------------------------------------------
    def _ensure_session(
        self, request: RuntimeRequest
    ) -> Tuple[ConversationSession, bool]:
        """Return the conversation's ACTIVE session, creating it at most once.

        The single session-coordination path: if a tracked session exists and
        is still ACTIVE it is reused unchanged (never reconnected); a missing,
        stale, or non-ACTIVE session is replaced by exactly one new session
        created through the reused :class:`SessionService`. Returns the
        session snapshot and whether it was reused. A failed creation raises
        ``RuntimeError`` — no retries.
        """
        key = (request.conversation_id, request.employee_id)
        tracked_id = self._active_sessions.get(key)
        if tracked_id is not None:
            result = self.session_service.get_session(tracked_id)
            if (
                result.success
                and result.session is not None
                and result.session.is_active
            ):
                return result.session, True
            # Stale bookkeeping (closed/failed/unknown session): drop it and
            # fall through to exactly one create. No reconnect attempts.
            del self._active_sessions[key]

        result = self.session_service.create_session(
            request.conversation_id,
            request.employee_id,
            dict(request.metadata),
        )
        if not result.success or result.session is None:
            raise RuntimeError(
                "Failed to establish a live session for conversation "
                f"{request.conversation_id}."
            )
        self._active_sessions[key] = result.session.session_id
        return result.session, False

    # ------------------------------------------------------------------
    # Internals — memory coordination (runtime-private; never implements)
    # ------------------------------------------------------------------
    def _load_memory_context(
        self, owner: Optional[User], request: RuntimeRequest
    ) -> Optional[int]:
        """Request conversation context from the reused memory service.

        Coordination only: delegates to the Sprint 9.1
        :class:`MemoryRetrievalService` (ownership validated upstream, exactly
        as that service documents) and reports how many context messages exist.
        Skipped (returns ``None``) when no owner or no retrieval service is
        available. The runtime never reads, ranks, filters, or injects the
        messages — interpretation belongs to the services that own it.
        """
        if owner is None or self.memory_retrieval is None:
            return None
        messages = self.memory_retrieval.retrieve(
            owner, request.employee_id, request.conversation_id
        )
        return len(messages)

    def _store_turn(
        self, context: RuntimeContext, text_out: Optional[str]
    ) -> None:
        """Store a completed text turn via the reused persistence service.

        Coordination only: delegates to the Sprint 8.1
        :class:`MemoryPersistenceService` (which owns the transaction and the
        write logic). Runs only for TEXT turns that produced a non-empty reply
        and only when an ``owner`` and a persistence service are available —
        audio/visual/document/action turn storage is intentionally out of
        scope for this sprint. The stored :class:`AIResponse` is a pure
        translation of the routed output: ``provider`` is the port's neutral
        name, ``language`` is the neutral ``"auto"`` placeholder (the runtime
        performs no language detection), and ``prompt_message_count`` is 1
        (the single live turn sent). Persistence exceptions propagate.
        """
        if context.request_type is not RuntimeRequestType.TEXT:
            return
        if context.owner is None or self.memory_persistence is None:
            return
        if not text_out or not text_out.strip():
            return
        request = context.request
        self.memory_persistence.persist(
            context.owner,
            request.employee_id,
            request.conversation_id,
            request.text,
            AIResponse(
                content=text_out,
                metadata=AIResponseMetadata(
                    provider=self.live_messaging.name,
                    language="auto",
                    employee_id=request.employee_id,
                    conversation_id=request.conversation_id,
                    prompt_message_count=1,
                ),
            ),
        )
