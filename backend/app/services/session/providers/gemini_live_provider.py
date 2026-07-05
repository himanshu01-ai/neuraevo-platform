"""Gemini Live session provider — real Live lifecycle (Sprint 12.8).

First concrete :class:`SessionProvider` that opens a **real** Gemini Live session
through Google's official ``google-genai`` SDK, via the frozen Session SPI. This
sprint intentionally stops after connection establishment and clean termination:
it opens and closes a Live session but exchanges no messages and performs no
streaming, audio, video, or tool execution.

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
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from app.services.multimodal_ai.adapters import GenAIClientProtocol
from app.services.multimodal_ai.providers import ProviderConfig
from app.services.session.models import (
    ConversationSession,
    SessionResult,
    SessionState,
)
from app.services.session.providers.base import SessionProvider


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
        self, client: GenAIClientProtocol, config: ProviderConfig
    ) -> None:
        self.client = client
        self.config = config
        self._sessions: Dict[uuid.UUID, _ProviderSessionRecord] = {}
        # Lazily-started background event loop bridging the async Live API to the
        # synchronous SPI (created only when a real Live session is opened).
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_lock = threading.Lock()

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
        cm = self.client.aio.live.connect(model=model)
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
