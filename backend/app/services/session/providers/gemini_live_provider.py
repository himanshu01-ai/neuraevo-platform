"""Gemini Live session provider — real Live lifecycle (Sprint 12.8).

First concrete :class:`SessionProvider` that opens a **real** Gemini Live session
through Google's official ``google-genai`` SDK, via the frozen Session SPI. As of
Sprint 12.9 it supports bidirectional **text** messaging (one user text turn +
aggregated streamed text response), Sprint 12.10 bidirectional **audio
transport** (send/receive raw PCM audio chunks), and as of Sprint 12.11
**visual input messaging** (send a supported image and aggregate the streamed
textual explanation), and as of Sprint 12.12 **document intelligence** (send a
supported document and aggregate the streamed explanation), and as of Sprint
12.13 an **action execution layer** that translates Gemini Live tool/function
requests into provider-independent :class:`ActionRequest`s and forwards them into
the existing Sprint 11 execution pipeline (planner -> registry -> permission ->
tool execution) via the private ``_ActionBridge`` — the provider never executes a
tool itself. It intentionally stops before Runtime integration, autonomous
planning, background execution, memory, multi-step reasoning, OCR, embeddings,
retrieval, image editing, and microphone/speaker/UI. Audio crosses the boundary
as ``bytes``, visual input as :class:`VisualInput`, and documents as
:class:`DocumentInput`; the SDK's audio/visual/document structures and mime types
stay hidden inside the private ``_AudioTransport`` / ``_VisualTransport`` /
``_DocumentTransport``.

The Live API is async-only (``client.aio.live.connect``), while the Session SPI
is synchronous; the provider bridges the two through a provider-private
background event loop, so the async connection is opened, held, and closed from
the synchronous SPI methods. The raw SDK session never escapes the provider — it
is wrapped in the private :class:`_LiveSessionHandle`, and the public
:class:`ConversationSession` DTO and Session SPI are unchanged.

Collaborators (a :class:`GenAIClientProtocol` and a :class:`ProviderConfig`) are
injected; the provider never constructs an SDK client, reads the environment, or
imports the SDK itself (it uses the injected client's Live surface). The model is
taken from ``create_session`` metadata (falling back to
``ProviderConfig.default_model``) — never hardcoded. Every failure path and every
successful close routes through the single :meth:`_cleanup_session` helper, so no
SDK resource is leaked and no cleanup logic is duplicated.
"""

import asyncio
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.services.multimodal_ai.adapters import GenAIClientProtocol
from app.services.multimodal_ai.providers import ProviderConfig
from app.services.permissions import PermissionRequest
from app.services.tools import ToolExecutionRequest
from app.services.session.models import (
    ConversationSession,
    SessionResult,
    SessionState,
)
from app.services.session.providers.base import SessionProvider


class VisualSource(str, Enum):
    """The origin of a visual input. Used ONLY for metadata — the provider's
    behavior never depends on the source value.

    - ``image``: a gallery / uploaded image.
    - ``screenshot``: a captured screen image.
    - ``camera_frame``: a still frame from a camera.
    - ``document_page``: a rendered document page (already converted to an image).
    - ``whiteboard``: a whiteboard photo.
    - ``diagram``: a diagram image.
    - ``other``: any other visual origin.
    """

    IMAGE = "image"
    SCREENSHOT = "screenshot"
    CAMERA_FRAME = "camera_frame"
    DOCUMENT_PAGE = "document_page"
    WHITEBOARD = "whiteboard"
    DIAGRAM = "diagram"
    OTHER = "other"


class VisualInput(BaseModel):
    """Immutable, provider-independent visual input (never carries SDK objects).

    ``payload`` is the raw image bytes; ``mime_type`` is the image MIME type (only
    ``image/jpeg`` / ``image/png`` / ``image/webp`` are supported); ``source``
    tags the origin (metadata only — behavior never depends on it); ``metadata``
    is opaque caller context (an optional ``prompt`` entry accompanies the image).
    ``frozen=True`` makes instances immutable. Native PDF/DOCX/PPTX/XLSX are not
    supported here — those belong to Sprint 12.12.
    """

    model_config = ConfigDict(frozen=True)

    payload: bytes
    mime_type: str
    source: VisualSource
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentType(str, Enum):
    """The kind of a document. Exists ONLY as metadata — the provider's behavior
    never branches on it; behavior is determined only by payload + MIME type.
    """

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    JSON = "json"
    OTHER = "other"


class DocumentInput(BaseModel):
    """Immutable, provider-independent document input (never carries SDK objects).

    ``payload`` is the raw document bytes; ``mime_type`` is the document MIME type
    (only the Sprint 12.12 supported set is accepted); ``document_type`` tags the
    kind (metadata only — behavior never depends on it); ``metadata`` is opaque
    caller context (an optional ``prompt`` entry accompanies the document, exactly
    like Sprint 12.11). ``frozen=True`` makes instances immutable.
    """

    model_config = ConfigDict(frozen=True)

    payload: bytes
    mime_type: str
    document_type: DocumentType
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionRequest(BaseModel):
    """Immutable, provider-independent request to run a tool/action.

    Normalized from a Gemini Live function/tool call — never carries SDK
    structures. ``tool_name`` names the tool; ``arguments`` are its inputs;
    ``metadata`` carries opaque call context (e.g. the SDK ``call_id``, kept only
    to correlate the response). ``frozen=True`` makes instances immutable.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: str
    arguments: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    """Immutable, provider-independent result of running a tool/action.

    ``success`` is the outcome; ``result`` is the plain-text result (never an SDK
    object); ``metadata`` carries any extra plain context. ``frozen=True`` makes
    instances immutable.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    result: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class LiveSessionProtocol(Protocol):
    """Minimal structural view of the operations a live session will expose.

    Documents the surface a future streaming sprint will drive on the wrapped
    session, so no SDK-specific session class ever needs to leak. The provider
    keeps the raw SDK session opaque behind :class:`_LiveSessionHandle`; this
    protocol only describes intended capabilities.
    """

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def send(self, data: Any) -> None: ...

    def receive(self) -> Any: ...


@dataclass
class _LiveSessionHandle:
    """Provider-PRIVATE wrapper owning the raw SDK Live session (never escapes).

    Owns the opaque SDK ``AsyncSession`` object, the async context manager used
    to open/close it, and provider-specific metadata (the model). Hides every SDK
    type behind this wrapper so no concrete SDK object ever crosses the provider
    boundary; nothing here appears in a :class:`SessionResult`.
    """

    model: str
    cm: Any  # async context manager from client.aio.live.connect(...) (opaque)
    sdk_session: Any  # entered SDK AsyncSession (opaque; never exposed)


@dataclass
class _ProviderSessionRecord:
    """Provider-PRIVATE bookkeeping for one session (never leaves the provider).

    Pairs the public, provider-independent :class:`ConversationSession` snapshot
    with an optional live handle. The handle is present only while a real Live
    session is open, and is removed by :meth:`GeminiLiveSessionProvider._cleanup_session`.
    """

    session: ConversationSession
    handle: Optional[_LiveSessionHandle] = None


class _StreamAggregator:
    """Provider-PRIVATE aggregator for a streamed text response.

    Collects text chunks in arrival order, ignores empty/``None`` payloads, and
    joins them into one complete string. Only the provider knows this exists — no
    SDK stream object or event is ever exposed through it.
    """

    def __init__(self) -> None:
        self._chunks: List[str] = []

    def add(self, chunk: Optional[str]) -> None:
        """Append a non-empty text chunk, preserving order (empties ignored)."""
        if chunk:
            self._chunks.append(chunk)

    def result(self) -> str:
        """Return the ordered chunks joined into one complete string."""
        return "".join(self._chunks)


class _AudioTransport:
    """Provider-PRIVATE audio (de)serialization; hides SDK audio structures.

    Owns the audio format details (16-bit PCM), encodes an outgoing PCM chunk
    into the SDK realtime-input blob, decodes an incoming SDK message into raw
    provider-independent bytes, and knows the supported chunk format. The rest of
    the application never sees SDK audio structures or mime types — only ``bytes``
    cross the provider boundary.
    """

    INPUT_MIME_TYPE = "audio/pcm;rate=16000"
    _SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM

    def is_supported_format(self, pcm_chunk: bytes) -> bool:
        """Whether ``pcm_chunk`` is 16-bit-PCM aligned (even byte length)."""
        return len(pcm_chunk) % self._SAMPLE_WIDTH_BYTES == 0

    def encode_outgoing(self, pcm_chunk: bytes) -> Dict[str, Any]:
        """Wrap validated PCM bytes as an SDK realtime-input audio blob (dict)."""
        return {"data": bytes(pcm_chunk), "mime_type": self.INPUT_MIME_TYPE}

    def extract_incoming(self, message: Any) -> Optional[bytes]:
        """Return raw audio bytes from one SDK message, or ``None`` if empty."""
        data = getattr(message, "data", None)
        if isinstance(data, (bytes, bytearray)) and len(data) > 0:
            return bytes(data)
        return None


class _VisualTransport:
    """Provider-PRIVATE visual (de)serialization; hides SDK visual structures.

    Owns the supported image MIME types, checks a MIME type, encodes a
    :class:`VisualInput` into SDK content parts (an inline-data image part plus an
    optional caller-supplied text prompt from ``metadata['prompt']``), and decodes
    an SDK response message into plain text. The rest of the application never
    sees SDK visual formats — only :class:`VisualInput` in and ``str`` out.
    """

    SUPPORTED_MIME_TYPES = frozenset(
        {"image/jpeg", "image/png", "image/webp"}
    )
    _PROMPT_METADATA_KEY = "prompt"

    def is_supported_mime(self, mime_type: Any) -> bool:
        """Whether ``mime_type`` is a supported image MIME type."""
        return mime_type in self.SUPPORTED_MIME_TYPES

    def encode_parts(self, visual_input: "VisualInput") -> List[Dict[str, Any]]:
        """Encode a VisualInput into SDK content parts (image + optional prompt)."""
        parts: List[Dict[str, Any]] = [
            {
                "inline_data": {
                    "mime_type": visual_input.mime_type,
                    "data": bytes(visual_input.payload),
                }
            }
        ]
        prompt = visual_input.metadata.get(self._PROMPT_METADATA_KEY)
        if isinstance(prompt, str) and prompt.strip():
            parts.append({"text": prompt})
        return parts

    def decode_response_text(self, message: Any) -> Optional[str]:
        """Extract plain text from one SDK response message (never the SDK object).

        Prefers a text part; falls back to the server-side output transcription.
        """
        text = getattr(message, "text", None)
        if text:
            return text
        server_content = getattr(message, "server_content", None)
        transcription = getattr(server_content, "output_transcription", None)
        if transcription is not None:
            return getattr(transcription, "text", None)
        return None


class _DocumentTransport:
    """Provider-PRIVATE document (de)serialization; hides SDK document structures.

    Owns the supported document MIME types, checks a MIME type, encodes ordered
    document chunks into SDK content parts (inline-data parts plus an optional
    caller-supplied text prompt from ``metadata['prompt']``), and decodes an SDK
    response message into plain text. No other module knows SDK document formats —
    only :class:`DocumentInput` in and ``str`` out.
    """

    SUPPORTED_MIME_TYPES = frozenset(
        {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/markdown",
            "text/csv",
            "application/json",
        }
    )
    _PROMPT_METADATA_KEY = "prompt"

    def is_supported_mime(self, mime_type: Any) -> bool:
        """Whether ``mime_type`` is a supported document MIME type."""
        return mime_type in self.SUPPORTED_MIME_TYPES

    def encode_parts(
        self, document_input: "DocumentInput", chunks: List[bytes]
    ) -> List[Dict[str, Any]]:
        """Encode ordered document chunks into SDK content parts (+ optional prompt)."""
        parts: List[Dict[str, Any]] = [
            {
                "inline_data": {
                    "mime_type": document_input.mime_type,
                    "data": bytes(chunk),
                }
            }
            for chunk in chunks
        ]
        prompt = document_input.metadata.get(self._PROMPT_METADATA_KEY)
        if isinstance(prompt, str) and prompt.strip():
            parts.append({"text": prompt})
        return parts

    def decode_response_text(self, message: Any) -> Optional[str]:
        """Extract plain text from one SDK response message (never the SDK object).

        Prefers a text part; falls back to the server-side output transcription.
        """
        text = getattr(message, "text", None)
        if text:
            return text
        server_content = getattr(message, "server_content", None)
        transcription = getattr(server_content, "output_transcription", None)
        if transcription is not None:
            return getattr(transcription, "text", None)
        return None


class _DocumentChunker:
    """Provider-PRIVATE document chunking extension point (single chunk for now).

    Determines whether a document needs chunking and exposes an ordered iterator
    of logical chunks. This sprint always yields exactly ONE chunk (the whole
    payload) for supported documents — large-document chunking, semantic
    chunking, and embeddings are intentionally NOT implemented. It exists only as
    a future extension seam.
    """

    def requires_chunking(self, document_input: "DocumentInput") -> bool:
        """Whether the document needs splitting (always ``False`` this sprint)."""
        return False

    def iter_chunks(self, document_input: "DocumentInput") -> Iterator[bytes]:
        """Yield ordered logical chunks — currently the single whole payload."""
        yield bytes(document_input.payload)


class _ActionBridge:
    """Provider-PRIVATE bridge: Gemini Live tool calls <-> Sprint 11 execution.

    The provider NEVER executes a tool. This bridge only translates and forwards:

    * detects Gemini Live tool/function requests in an SDK message and normalizes
      them into provider-independent :class:`ActionRequest`s (hiding SDK
      structures),
    * forwards an :class:`ActionRequest` into the EXISTING Sprint 11 execution
      pipeline — planner -> tool registry -> permission service -> tool execution
      service — all injected and reused unchanged (no new execution framework),
    * receives the Sprint 11 ``ToolExecutionResult`` and maps it to an
      :class:`ActionResult`, and
    * converts an :class:`ActionResult` back into a Gemini-compatible function
      response (hiding SDK structures).

    Because the model already selected the concrete tool + arguments (Gemini
    function calling), the planner is invoked as the pipeline's planning gate
    while the concrete tool + arguments flow unchanged through registry ->
    permission -> execution — so the model's arguments are never lost. The four
    Sprint 11 collaborators remain the single source of execution; nothing here
    plans, resolves, permissions, or executes a tool itself.
    """

    def __init__(
        self, planner, tool_registry, permissions, tool_execution
    ) -> None:
        self._planner = planner
        self._tool_registry = tool_registry
        self._permissions = permissions
        self._tool_execution = tool_execution

    def is_configured(self) -> bool:
        """Whether the full Sprint 11 execution pipeline is available."""
        return None not in (
            self._planner,
            self._tool_registry,
            self._permissions,
            self._tool_execution,
        )

    def extract_action_requests(self, message: Any) -> List["ActionRequest"]:
        """Detect Gemini Live function calls in one SDK message -> ActionRequests.

        Returns an empty list when the message carries no tool call. No SDK tool
        structure escapes — only provider-independent :class:`ActionRequest`s.
        """
        tool_call = getattr(message, "tool_call", None)
        if tool_call is None:
            return []
        function_calls = getattr(tool_call, "function_calls", None) or []
        requests: List["ActionRequest"] = []
        for call in function_calls:
            name = getattr(call, "name", None)
            if not isinstance(name, str) or not name:
                continue
            args = getattr(call, "args", None) or {}
            call_id = getattr(call, "id", None)
            requests.append(
                ActionRequest(
                    tool_name=name,
                    arguments=dict(args),
                    metadata={"call_id": call_id} if call_id else {},
                )
            )
        return requests

    def to_function_response(
        self, action_request: "ActionRequest", action_result: "ActionResult"
    ) -> Dict[str, Any]:
        """Convert an ActionResult into a Gemini-compatible function response.

        A plain dict (never an SDK object) suitable for ``send_tool_response``.
        """
        function_response: Dict[str, Any] = {
            "name": action_request.tool_name,
            "response": {
                "success": action_result.success,
                "result": action_result.result,
            },
        }
        call_id = action_request.metadata.get("call_id")
        if call_id:
            function_response["id"] = call_id
        return {"function_responses": [function_response]}

    def execute(self, action_request: "ActionRequest") -> "ActionResult":
        """Forward an ActionRequest through the Sprint 11 pipeline; return ActionResult.

        The provider never executes: each step delegates to the reused Sprint 11
        service. Order is exact: planner -> registry -> permission -> execution.
        A permission denial short-circuits to an unsuccessful ActionResult; every
        service exception propagates unchanged.
        """
        if not self.is_configured():
            raise RuntimeError(
                "Action execution is unavailable: the Sprint 11 execution "
                "pipeline (planner/registry/permission/tool-execution) is not "
                "configured on this provider."
            )

        # 1. Planner (Sprint 11.4) — planning gate for the requested action.
        self._planner.create_plan(action_request.tool_name)

        # 2. Tool Registry (Sprint 11.2) — resolve the tool (KeyError if unknown).
        self._tool_registry.get_tool(action_request.tool_name)

        # 3. Permission Service (Sprint 11.3) — gate the tool + arguments.
        permission = self._permissions.check_permission(
            PermissionRequest(
                tool_name=action_request.tool_name,
                arguments=action_request.arguments,
            )
        )
        if not permission.approved or permission.requires_user_confirmation:
            return ActionResult(
                success=False,
                result=permission.reason or "permission denied",
                metadata={"permission_denied": True},
            )

        # 4. Tool Execution (Sprint 11.1) — the ONLY executor (never the provider).
        tool_result = self._tool_execution.execute(
            ToolExecutionRequest(
                tool_name=action_request.tool_name,
                arguments=action_request.arguments,
            )
        )
        return ActionResult(
            success=bool(tool_result.success),
            result="" if tool_result.output is None else str(tool_result.output),
            metadata={},
        )


class GeminiLiveSessionProvider(SessionProvider):
    """Concrete :class:`SessionProvider` opening a real Gemini Live session.

    Constructor-injected with a :class:`GenAIClientProtocol` and a
    :class:`ProviderConfig`; it never builds an SDK object, reads the
    environment, or holds a global/singleton. Public attributes are exactly the
    injected collaborators (``client``, ``config``); all session state and the
    async bridge machinery are private. Every lifecycle change runs through
    :meth:`_validate_transition`; every teardown through :meth:`_cleanup_session`.
    """

    name = "gemini_live"

    # Request-metadata key through which the caller supplies the Live model
    # (falls back to ProviderConfig.default_model). Never a hardcoded model name.
    _MODEL_METADATA_KEY = "model"
    _CONNECT_TIMEOUT_SECONDS = 30.0
    _CLOSE_TIMEOUT_SECONDS = 10.0
    _SEND_TIMEOUT_SECONDS = 30.0
    _RECEIVE_TIMEOUT_SECONDS = 60.0
    # Connect-time config: enable server-side text transcription of the model's
    # response so a complete text string can be aggregated from Live models. Only
    # the text transcript is consumed — no audio bytes, mic, or speaker.
    _LIVE_CONNECT_CONFIG: Dict[str, Any] = {"output_audio_transcription": {}}

    # Allowed lifecycle transitions (unchanged from Sprint 12.7):
    #   CREATED -> ACTIVE -> PAUSED -> ACTIVE -> CLOSED ; FAILED from any live
    #   state. CLOSED and FAILED are terminal. ``create_session`` now drives
    #   CREATED -> ACTIVE on a successful connect, or CREATED -> FAILED on error.
    _ALLOWED_TRANSITIONS: Dict[SessionState, frozenset] = {
        SessionState.CREATED: frozenset(
            {SessionState.ACTIVE, SessionState.FAILED}
        ),
        SessionState.ACTIVE: frozenset(
            {SessionState.PAUSED, SessionState.CLOSED, SessionState.FAILED}
        ),
        SessionState.PAUSED: frozenset(
            {SessionState.ACTIVE, SessionState.FAILED}
        ),
        SessionState.CLOSED: frozenset(),
        SessionState.FAILED: frozenset(),
    }

    def __init__(
        self,
        client: GenAIClientProtocol,
        config: ProviderConfig,
        planner: Any = None,
        tool_registry: Any = None,
        permissions: Any = None,
        tool_execution: Any = None,
    ) -> None:
        self.client = client
        self.config = config
        self._sessions: Dict[uuid.UUID, _ProviderSessionRecord] = {}
        # Lazily-started background event loop bridging the async Live API to the
        # synchronous SPI (created only when a real Live session is opened).
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_lock = threading.Lock()
        # Provider-private audio (de)serialization; hides SDK audio structures.
        self._audio_transport = _AudioTransport()
        # Provider-private visual (de)serialization; hides SDK visual structures.
        self._visual_transport = _VisualTransport()
        # Provider-private document (de)serialization + chunking extension point.
        self._document_transport = _DocumentTransport()
        self._document_chunker = _DocumentChunker()
        # Provider-private bridge to the existing Sprint 11 execution pipeline.
        # The provider only translates/forwards — it never executes tools itself.
        self._action_bridge = _ActionBridge(
            planner, tool_registry, permissions, tool_execution
        )

    # ------------------------------------------------------------------
    # Session SPI
    # ------------------------------------------------------------------
    def create_session(
        self,
        conversation_id: uuid.UUID,
        employee_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionResult:
        """Open ONE real Gemini Live session; ``ACTIVE`` on success.

        Builds a ``CREATED`` session, opens exactly one Live connection, stores
        the SDK handle privately, and transitions to ``ACTIVE``. On any
        connection failure it cleans up resources, transitions to ``FAILED``, and
        returns ``SessionResult(success=False)``. No retries, no reconnection, no
        message exchange, no streaming.
        """
        now = datetime.now(timezone.utc)
        session = ConversationSession(
            session_id=uuid.uuid4(),
            conversation_id=conversation_id,
            employee_id=employee_id,
            state=SessionState.CREATED,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        record = _ProviderSessionRecord(session=session)
        self._sessions[session.session_id] = record

        try:
            handle = self._open_live_session(self._resolve_model(metadata))
        except Exception:
            self._cleanup_session(record)
            record.session = self._apply_state(
                record.session, SessionState.FAILED
            )
            return SessionResult(success=False, session=record.session)

        record.handle = handle
        record.session = self._apply_state(record.session, SessionState.ACTIVE)
        return SessionResult(success=True, session=record.session)

    def pause_session(self, session_id: uuid.UUID) -> SessionResult:
        """Transition a session to ``PAUSED`` (valid only from ``ACTIVE``)."""
        return self._transition(session_id, SessionState.PAUSED)

    def resume_session(self, session_id: uuid.UUID) -> SessionResult:
        """Transition a session to ``ACTIVE`` (valid from ``CREATED``/``PAUSED``)."""
        return self._transition(session_id, SessionState.ACTIVE)

    def close_session(self, session_id: uuid.UUID) -> SessionResult:
        """Close the real Live session and transition to ``CLOSED``.

        Validates the transition, releases every SDK resource and removes the
        provider-private handle via :meth:`_cleanup_session`, then records the
        ``CLOSED`` state. No leaks.
        """
        record = self._sessions.get(session_id)
        if record is None:
            return SessionResult(success=False, session=None)
        self._validate_transition(record.session.state, SessionState.CLOSED)
        self._cleanup_session(record)
        record.session = self._apply_state(record.session, SessionState.CLOSED)
        return SessionResult(success=True, session=record.session)

    def get_session(self, session_id: uuid.UUID) -> SessionResult:
        """Return the current snapshot of a session, or a soft failure."""
        record = self._sessions.get(session_id)
        if record is None:
            return SessionResult(success=False, session=None)
        return SessionResult(success=True, session=record.session)

    def health_check(self) -> bool:
        """Report readiness using ONLY the injected client; never raises.

        Uses the lightest client capability (``models.list``) — it opens no Live
        session, generates no content, and consumes no tokens. Any failure yields
        ``False``.
        """
        try:
            self.client.models.list()
        except Exception:
            return False
        return True

    # ------------------------------------------------------------------
    # Live text messaging (provider-specific; NOT part of the Session SPI)
    # ------------------------------------------------------------------
    def send_message(
        self, session_id: uuid.UUID, message: str
    ) -> SessionResult:
        """Send exactly ONE user text message over an ACTIVE Live session.

        Validates the session is present and ACTIVE, then sends a single
        user-role text turn. No retries, prompt engineering, planner, memory, or
        tools. Returns the (unchanged) ACTIVE session snapshot. SDK exceptions
        propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        self._run_async(
            self._asend(record.handle.sdk_session, message),
            self._SEND_TIMEOUT_SECONDS,
        )
        return SessionResult(success=True, session=record.session)

    def receive_response(self, session_id: uuid.UUID) -> str:
        """Aggregate the streamed text response into one complete string.

        Validates the session is present and ACTIVE, consumes the streamed
        response exactly once (order preserved, empty chunks ignored), and
        returns the joined text. No SDK stream object is ever exposed; SDK
        exceptions propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        return self._run_async(
            self._acollect(record.handle.sdk_session),
            self._RECEIVE_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Live audio transport (provider-specific; NOT part of the Session SPI)
    # ------------------------------------------------------------------
    def send_audio_chunk(
        self, session_id: uuid.UUID, pcm_chunk: bytes
    ) -> SessionResult:
        """Send exactly ONE PCM audio chunk over an ACTIVE Live session.

        Validates the session is present and ACTIVE, validates the chunk via the
        single :meth:`_validate_audio_chunk` helper, and sends exactly one
        realtime-audio blob (the SDK format is hidden by ``_AudioTransport``). No
        retries, buffering, planner, memory, or runtime. Returns the unchanged
        ACTIVE snapshot; SDK exceptions propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        validated = self._validate_audio_chunk(pcm_chunk)
        self._run_async(
            self._asend_audio(record.handle.sdk_session, validated),
            self._SEND_TIMEOUT_SECONDS,
        )
        return SessionResult(success=True, session=record.session)

    def receive_audio_chunk(self, session_id: uuid.UUID) -> bytes:
        """Aggregate the streamed audio response into provider-independent bytes.

        Validates the session is present and ACTIVE, consumes the streamed audio
        exactly once (order preserved, empty chunks ignored), and returns the
        concatenated raw bytes. No SDK audio object is ever exposed; SDK
        exceptions propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        return self._run_async(
            self._acollect_audio(record.handle.sdk_session),
            self._RECEIVE_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Live visual input (provider-specific; NOT part of the Session SPI)
    # ------------------------------------------------------------------
    def send_visual_input(
        self, session_id: uuid.UUID, visual_input: "VisualInput"
    ) -> SessionResult:
        """Send exactly ONE visual message over an ACTIVE Live session.

        Validates the session is present and ACTIVE and validates the
        :class:`VisualInput` via the single :meth:`_validate_visual_input` helper,
        then sends exactly one content turn (the SDK visual format is hidden by
        ``_VisualTransport``). No retries, buffering, prompt engineering, planner,
        memory, or runtime. Returns the unchanged ACTIVE snapshot; SDK exceptions
        propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        validated = self._validate_visual_input(visual_input)
        self._run_async(
            self._asend_visual(record.handle.sdk_session, validated),
            self._SEND_TIMEOUT_SECONDS,
        )
        return SessionResult(success=True, session=record.session)

    def receive_visual_response(self, session_id: uuid.UUID) -> str:
        """Aggregate the streamed textual explanation into one complete string.

        Validates the session is present and ACTIVE, consumes the streamed
        response exactly once (order preserved, empty chunks ignored), and returns
        the joined text. No SDK object is ever exposed; SDK exceptions propagate
        unchanged.
        """
        record = self._validate_active_session(session_id)
        return self._run_async(
            self._acollect_visual(record.handle.sdk_session),
            self._RECEIVE_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Live document intelligence (provider-specific; NOT part of the SPI)
    # ------------------------------------------------------------------
    def send_document(
        self, session_id: uuid.UUID, document_input: "DocumentInput"
    ) -> SessionResult:
        """Send exactly ONE document over an ACTIVE Live session.

        Validates the session is present and ACTIVE and validates the
        :class:`DocumentInput` via the single :meth:`_validate_document_input`
        helper, then sends exactly one content turn built from the ordered
        chunk(s) (currently one) — the SDK document format is hidden by
        ``_DocumentTransport``. An optional ``metadata['prompt']`` accompanies the
        document (exactly like Sprint 12.11). No retries, buffering, prompt
        engineering, planner, memory, or runtime. Returns the unchanged ACTIVE
        snapshot; SDK exceptions propagate unchanged.
        """
        record = self._validate_active_session(session_id)
        validated = self._validate_document_input(document_input)
        chunks = list(self._document_chunker.iter_chunks(validated))
        self._run_async(
            self._asend_document(record.handle.sdk_session, validated, chunks),
            self._SEND_TIMEOUT_SECONDS,
        )
        return SessionResult(success=True, session=record.session)

    def receive_document_response(self, session_id: uuid.UUID) -> str:
        """Aggregate the streamed textual explanation into one complete string.

        Validates the session is present and ACTIVE, consumes the streamed
        response exactly once (order preserved, empty chunks ignored), and returns
        the joined text. No SDK object is ever exposed; SDK exceptions propagate
        unchanged.
        """
        record = self._validate_active_session(session_id)
        return self._run_async(
            self._acollect_document(record.handle.sdk_session),
            self._RECEIVE_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Action execution (provider-specific; translation only — NOT the SPI)
    # ------------------------------------------------------------------
    def execute_action(
        self, session_id: uuid.UUID, action_request: "ActionRequest"
    ) -> "ActionResult":
        """Translate + forward an action into the Sprint 11 pipeline; return ActionResult.

        The provider ONLY translates and forwards: it validates the ACTIVE session
        and the :class:`ActionRequest` (single :meth:`_validate_action_request`
        helper), then hands the request to the private ``_ActionBridge``, which
        drives the existing Sprint 11 pipeline (planner -> registry -> permission
        -> tool execution). The provider never plans, permissions, or executes a
        tool itself; every Sprint 11 exception propagates unchanged.
        """
        self._validate_active_session(session_id)
        validated = self._validate_action_request(action_request)
        return self._action_bridge.execute(validated)

    # ------------------------------------------------------------------
    # Internals — lifecycle state (provider-private)
    # ------------------------------------------------------------------
    def _resolve_model(self, metadata: Optional[Dict[str, Any]]) -> str:
        """Return the Live model from metadata, else ``config.default_model``."""
        if metadata:
            candidate = metadata.get(self._MODEL_METADATA_KEY)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return self.config.default_model

    def _validate_transition(
        self, current_state: SessionState, target_state: SessionState
    ) -> None:
        """Raise ``ValueError`` if ``current_state -> target_state`` is invalid."""
        if target_state not in self._ALLOWED_TRANSITIONS.get(
            current_state, frozenset()
        ):
            raise ValueError(
                f"Invalid session transition: "
                f"{current_state.value} -> {target_state.value}"
            )

    def _apply_state(
        self, session: ConversationSession, target_state: SessionState
    ) -> ConversationSession:
        """Validate and produce a new session snapshot in ``target_state``."""
        self._validate_transition(session.state, target_state)
        return session.model_copy(
            update={
                "state": target_state,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    def _transition(
        self, session_id: uuid.UUID, target_state: SessionState
    ) -> SessionResult:
        """State-only lifecycle transition (no SDK effect)."""
        record = self._sessions.get(session_id)
        if record is None:
            return SessionResult(success=False, session=None)
        record.session = self._apply_state(record.session, target_state)
        return SessionResult(success=True, session=record.session)

    # ------------------------------------------------------------------
    # Internals — SDK bridge (async Live API <-> sync SPI); provider-private
    # ------------------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """Return the provider's background event loop, starting it on demand."""
        with self._loop_lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever,
                    name="gemini-live-session-loop",
                    daemon=True,
                )
                thread.start()
                self._loop = loop
                self._loop_thread = thread
        return self._loop

    def _run_async(self, coro: Any, timeout: float) -> Any:
        """Run ``coro`` on the background loop and block for its result."""
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    def _open_live_session(self, model: str) -> _LiveSessionHandle:
        """Open exactly one real Live session and wrap it privately.

        Uses the injected client's async Live surface; the connection is
        established on the background loop. Raises on failure (caller handles
        cleanup + ``FAILED``).
        """
        cm = self.client.aio.live.connect(
            model=model, config=self._LIVE_CONNECT_CONFIG
        )
        sdk_session = self._run_async(
            cm.__aenter__(), self._CONNECT_TIMEOUT_SECONDS
        )
        return _LiveSessionHandle(model=model, cm=cm, sdk_session=sdk_session)

    def _close_live_session(self, handle: _LiveSessionHandle) -> None:
        """Close the real SDK session symmetrically on the background loop."""
        self._run_async(
            handle.cm.__aexit__(None, None, None),
            self._CLOSE_TIMEOUT_SECONDS,
        )

    def _cleanup_session(self, record: _ProviderSessionRecord) -> None:
        """Release the SDK resource and drop the private handle (never raises).

        The single teardown path: called on every connection-failure path and on
        every successful close, so no SDK resource is leaked and no cleanup logic
        is duplicated. Best-effort — cleanup failures are swallowed.
        """
        handle = record.handle
        record.handle = None
        if handle is None:
            return
        try:
            self._close_live_session(handle)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internals — messaging (provider-private)
    # ------------------------------------------------------------------
    def _validate_active_session(
        self, session_id: uuid.UUID
    ) -> _ProviderSessionRecord:
        """Return the record for an existing ACTIVE session, else ``ValueError``.

        The single validation path for send/receive: rejects a missing session
        and a non-ACTIVE (or handle-less) session with a ``ValueError``, so the
        exists+ACTIVE check is never duplicated.
        """
        record = self._sessions.get(session_id)
        if record is None:
            raise ValueError(f"Session not found: {session_id}")
        if record.session.state != SessionState.ACTIVE or record.handle is None:
            raise ValueError(
                f"Session is not ACTIVE: {record.session.state.value}"
            )
        return record

    async def _asend(self, sdk_session: Any, message: str) -> None:
        """Send exactly one user-role text turn over the SDK Live session."""
        await sdk_session.send_client_content(
            turns={"role": "user", "parts": [{"text": message}]},
            turn_complete=True,
        )

    async def _acollect(self, sdk_session: Any) -> str:
        """Consume the streamed response once and aggregate its text chunks."""
        aggregator = _StreamAggregator()
        async for message in sdk_session.receive():
            aggregator.add(self._extract_text(message))
        return aggregator.result()

    @staticmethod
    def _extract_text(message: Any) -> Optional[str]:
        """Extract plain text from one SDK stream message (never the SDK object).

        Prefers a text part; falls back to the server-side output transcription
        (Live models that respond in audio). Returns ``None`` when the message
        carries no text.
        """
        text = getattr(message, "text", None)
        if text:
            return text
        server_content = getattr(message, "server_content", None)
        transcription = getattr(server_content, "output_transcription", None)
        if transcription is not None:
            return getattr(transcription, "text", None)
        return None

    # ------------------------------------------------------------------
    # Internals — audio transport (provider-private)
    # ------------------------------------------------------------------
    def _validate_audio_chunk(self, pcm_chunk: Any) -> bytes:
        """Validate an outgoing audio chunk; the single audio-send validator.

        Ensures the input is bytes-like, non-empty, and a supported (16-bit PCM)
        format. Raises ``TypeError`` for non-bytes and ``ValueError`` for empty
        or malformed chunks. All audio sending routes through here, so the
        validation is never duplicated.
        """
        if not isinstance(pcm_chunk, (bytes, bytearray)):
            raise TypeError("audio chunk must be bytes-like (bytes/bytearray)")
        if len(pcm_chunk) == 0:
            raise ValueError("audio chunk must not be empty")
        if not self._audio_transport.is_supported_format(pcm_chunk):
            raise ValueError(
                "audio chunk must be 16-bit PCM (even byte length)"
            )
        return bytes(pcm_chunk)

    async def _asend_audio(self, sdk_session: Any, pcm_chunk: bytes) -> None:
        """Send exactly one realtime-audio blob over the SDK Live session."""
        await sdk_session.send_realtime_input(
            audio=self._audio_transport.encode_outgoing(pcm_chunk)
        )

    async def _acollect_audio(self, sdk_session: Any) -> bytes:
        """Consume the streamed audio response once and aggregate its bytes."""
        buffer = bytearray()
        async for message in sdk_session.receive():
            chunk = self._audio_transport.extract_incoming(message)
            if chunk:
                buffer.extend(chunk)
        return bytes(buffer)

    # ------------------------------------------------------------------
    # Internals — visual input (provider-private)
    # ------------------------------------------------------------------
    def _validate_visual_input(self, visual_input: Any) -> "VisualInput":
        """Validate an outgoing VisualInput; the single visual-send validator.

        Ensures the input is a :class:`VisualInput` with bytes-like, non-empty
        payload, a supported image MIME type, and a valid :class:`VisualSource`.
        Raises ``TypeError`` for wrong types and ``ValueError`` for empty payloads
        or unsupported MIME types. ``metadata`` is left untouched. All visual
        sending routes through here, so the validation is never duplicated.
        """
        if not isinstance(visual_input, VisualInput):
            raise TypeError("visual_input must be a VisualInput")
        if not isinstance(visual_input.payload, (bytes, bytearray)):
            raise TypeError("VisualInput.payload must be bytes")
        if len(visual_input.payload) == 0:
            raise ValueError("VisualInput.payload must not be empty")
        if not self._visual_transport.is_supported_mime(visual_input.mime_type):
            raise ValueError(
                f"Unsupported visual MIME type: {visual_input.mime_type}"
            )
        if not isinstance(visual_input.source, VisualSource):
            raise ValueError("VisualInput.source must be a VisualSource")
        return visual_input

    async def _asend_visual(
        self, sdk_session: Any, visual_input: "VisualInput"
    ) -> None:
        """Send exactly one visual content turn over the SDK Live session."""
        await sdk_session.send_client_content(
            turns={
                "role": "user",
                "parts": self._visual_transport.encode_parts(visual_input),
            },
            turn_complete=True,
        )

    async def _acollect_visual(self, sdk_session: Any) -> str:
        """Consume the streamed visual explanation once and aggregate its text."""
        aggregator = _StreamAggregator()
        async for message in sdk_session.receive():
            aggregator.add(self._visual_transport.decode_response_text(message))
        return aggregator.result()

    # ------------------------------------------------------------------
    # Internals — document intelligence (provider-private)
    # ------------------------------------------------------------------
    def _validate_document_input(self, document_input: Any) -> "DocumentInput":
        """Validate an outgoing DocumentInput; the single document-send validator.

        Ensures the input is a :class:`DocumentInput` with bytes-like, non-empty
        payload, a supported document MIME type, and a valid :class:`DocumentType`.
        Raises ``TypeError`` for wrong types and ``ValueError`` for empty payloads
        or unsupported MIME types. ``metadata`` is left untouched. All document
        sending routes through here, so the validation is never duplicated.
        """
        if not isinstance(document_input, DocumentInput):
            raise TypeError("document_input must be a DocumentInput")
        if not isinstance(document_input.payload, (bytes, bytearray)):
            raise TypeError("DocumentInput.payload must be bytes")
        if len(document_input.payload) == 0:
            raise ValueError("DocumentInput.payload must not be empty")
        if not self._document_transport.is_supported_mime(
            document_input.mime_type
        ):
            raise ValueError(
                f"Unsupported document MIME type: {document_input.mime_type}"
            )
        if not isinstance(document_input.document_type, DocumentType):
            raise ValueError(
                "DocumentInput.document_type must be a DocumentType"
            )
        return document_input

    async def _asend_document(
        self, sdk_session: Any, document_input: "DocumentInput", chunks: List[bytes]
    ) -> None:
        """Send exactly one document content turn over the SDK Live session."""
        await sdk_session.send_client_content(
            turns={
                "role": "user",
                "parts": self._document_transport.encode_parts(
                    document_input, chunks
                ),
            },
            turn_complete=True,
        )

    async def _acollect_document(self, sdk_session: Any) -> str:
        """Consume the streamed document explanation once and aggregate its text."""
        aggregator = _StreamAggregator()
        async for message in sdk_session.receive():
            aggregator.add(
                self._document_transport.decode_response_text(message)
            )
        return aggregator.result()

    # ------------------------------------------------------------------
    # Internals — action execution (provider-private)
    # ------------------------------------------------------------------
    def _validate_action_request(self, action_request: Any) -> "ActionRequest":
        """Validate an ActionRequest; the single action-request validator.

        Ensures the input is an :class:`ActionRequest` with a non-empty tool name
        and a dict of arguments. Raises ``TypeError`` for wrong types and
        ``ValueError`` for a missing/blank tool name. ``metadata`` is left
        untouched. Every action routes through here, so validation is never
        duplicated. Whether the tool actually exists is decided by the reused
        Sprint 11 tool registry (a ``KeyError`` from ``get_tool``), not here.
        """
        if not isinstance(action_request, ActionRequest):
            raise TypeError("action_request must be an ActionRequest")
        if not action_request.tool_name or not action_request.tool_name.strip():
            raise ValueError("ActionRequest.tool_name must be a non-empty string")
        if not isinstance(action_request.arguments, dict):
            raise TypeError("ActionRequest.arguments must be a dict")
        return action_request
