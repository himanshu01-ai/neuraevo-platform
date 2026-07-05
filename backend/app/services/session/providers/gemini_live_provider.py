"""
Gemini Live Session Provider

First concrete implementation of SessionProvider.

Implements Session SPI v1.

Intentionally stops before opening
real Live sessions.

Streaming begins in Sprint 12.8.
"""
"""Gemini Live session provider — first concrete SessionProvider (Sprint 12.7).

Implements the frozen Session SPI (Sprint 12.6) for a future Gemini Live backend.
This sprint integrates the injected Google GenAI client into the session layer
but intentionally stops BEFORE opening any real Live session: it performs no
networking, streaming, audio, WebSocket, or token generation. It owns ONLY
provider-specific lifecycle management over provider-private state.

Collaborators are injected (a :class:`GenAIClientProtocol` and a
:class:`ProviderConfig`); the provider never instantiates an SDK object, reads
the environment, creates a client, or holds a global/singleton. The concrete SDK
Live-session type never leaks: the provider depends only on the internal
:class:`LiveSessionProtocol`. The public :class:`ConversationSession` DTO and the
Session SPI are unchanged — all SDK/session-specific state is kept private.
"""

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
    """Minimal structural view of a live-session handle (for future work).

    Exposes only the operations later sprints will need to drive a real Gemini
    Live session, so no SDK-specific session class ever leaks outside this
    provider — the provider depends only on this protocol. This sprint opens no
    live session, so no instance is ever created; the protocol only types the
    private handle slot.
    """

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def send(self, data: Any) -> None: ...

    def receive(self) -> Any: ...


@dataclass
class _ProviderSessionRecord:
    """Provider-PRIVATE bookkeeping for one session (never leaves the provider).

    Pairs the public, provider-independent :class:`ConversationSession` snapshot
    with an optional live-session handle typed only as
    :class:`LiveSessionProtocol`. The handle stays ``None`` this sprint (no Live
    session is opened), but the slot keeps SDK/session-specific state internal so
    the public Session SPI and DTO never need to change.
    """

    session: ConversationSession
    live: Optional[LiveSessionProtocol] = None


class GeminiLiveSessionProvider(SessionProvider):
    """First concrete :class:`SessionProvider` — Gemini Live lifecycle only.

    Constructor-injected with a :class:`GenAIClientProtocol` and a
    :class:`ProviderConfig`; it never builds an SDK object, reads the
    environment, or creates clients/globals/singletons. It manages session
    lifecycle over provider-private state and opens no Live session, performs no
    networking/streaming/token generation in this sprint.

    Public attributes are exactly the injected collaborators (``client``,
    ``config``); all session bookkeeping is private (``_sessions``). Every
    lifecycle change runs through :meth:`_validate_transition`, so transition
    rules are defined in exactly one place.
    """

    name = "gemini_live"

    # Allowed lifecycle transitions, strictly per the Sprint 12.7 state diagram:
    #   CREATED -> ACTIVE -> PAUSED -> ACTIVE -> CLOSED
    #   FAILED may occur from any live (non-terminal) state.
    # CLOSED and FAILED are terminal (no outgoing transitions). ``resume`` is the
    # only "-> ACTIVE" operation, so it activates CREATED and resumes PAUSED.
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

    # ------------------------------------------------------------------
    # Session SPI
    # ------------------------------------------------------------------
    def create_session(
        self,
        conversation_id: uuid.UUID,
        employee_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionResult:
        """Create a provider-owned session in the ``CREATED`` state.

        No Live session is opened and no networking occurs — only a
        provider-independent :class:`ConversationSession` DTO is built and stored
        privately.
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
        self._sessions[session.session_id] = _ProviderSessionRecord(
            session=session
        )
        return SessionResult(success=True, session=session)

    def pause_session(self, session_id: uuid.UUID) -> SessionResult:
        """Transition a session to ``PAUSED`` (valid only from ``ACTIVE``)."""
        return self._transition(session_id, SessionState.PAUSED)

    def resume_session(self, session_id: uuid.UUID) -> SessionResult:
        """Transition a session to ``ACTIVE`` (valid from ``CREATED``/``PAUSED``)."""
        return self._transition(session_id, SessionState.ACTIVE)

    def close_session(self, session_id: uuid.UUID) -> SessionResult:
        """Transition a session to ``CLOSED`` (valid only from ``ACTIVE``)."""
        return self._transition(session_id, SessionState.CLOSED)

    def get_session(self, session_id: uuid.UUID) -> SessionResult:
        """Return the current snapshot of a session, or a soft failure."""
        record = self._sessions.get(session_id)
        if record is None:
            return SessionResult(success=False, session=None)
        return SessionResult(success=True, session=record.session)

    def health_check(self) -> bool:
        """Report readiness using ONLY the injected client; never raises.

        Uses the lightest client capability (``models.list``) — no session is
        created, no Live API is opened, no tokens are generated. Any failure
        yields ``False``.
        """
        try:
            self.client.models.list()
        except Exception:
            return False
        return True

    # ------------------------------------------------------------------
    # Internals (provider-private)
    # ------------------------------------------------------------------
    def _validate_transition(
        self, current_state: SessionState, target_state: SessionState
    ) -> None:
        """Raise ``ValueError`` if ``current_state -> target_state`` is invalid.

        The single source of transition truth; every lifecycle operation routes
        through it, so no transition logic is duplicated.
        """
        if target_state not in self._ALLOWED_TRANSITIONS.get(
            current_state, frozenset()
        ):
            raise ValueError(
                f"Invalid session transition: "
                f"{current_state.value} -> {target_state.value}"
            )

    def _transition(
        self, session_id: uuid.UUID, target_state: SessionState
    ) -> SessionResult:
        """Validate and apply a lifecycle transition, producing a new snapshot."""
        record = self._sessions.get(session_id)
        if record is None:
            return SessionResult(success=False, session=None)
        self._validate_transition(record.session.state, target_state)
        record.session = record.session.model_copy(
            update={
                "state": target_state,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return SessionResult(success=True, session=record.session)
