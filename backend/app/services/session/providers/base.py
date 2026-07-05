"""
SESSION SPI v1

This provider interface is considered stable.

Future session implementations
(Gemini Live, OpenAI Realtime,
Voice, MCP, Screen Sharing, etc.)

must implement this contract.

Breaking changes require a new SPI version.

Additive extensions only.
"""
"""Session provider contract (Sprint 12.6 — abstraction only).

Defines the replaceable interface that future session backends implement — e.g.
a Gemini Live session, an OpenAI Realtime session, or voice / screen-sharing /
collaborative / MCP sessions. This sprint ships ONLY the abstraction: no concrete
backend, no SDK, no networking, no streaming, no transport, no persistence.
Concrete providers — added in later sprints — own all backend specifics behind
this interface, isolated from services, repositories, models, and routers.
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.services.session.models import SessionResult


class SessionProvider(ABC):
    """Replaceable backend that manages long-lived interaction sessions.

    Concrete implementations (added in a later sprint) live behind this interface
    so the rest of the system stays backend-agnostic. ``name`` identifies the
    provider; the lifecycle methods create, pause, resume, close, and look up
    sessions; ``health_check`` reports backend readiness. This sprint provides
    only the abstract contract — there is no concrete provider yet, and nothing
    is streamed, transported, or persisted.
    """

    name: str

    @abstractmethod
    def create_session(
        self,
        conversation_id: uuid.UUID,
        employee_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionResult:
        """Create a new session for the given conversation and employee."""

    @abstractmethod
    def pause_session(self, session_id: uuid.UUID) -> SessionResult:
        """Pause an active session, leaving it resumable."""

    @abstractmethod
    def resume_session(self, session_id: uuid.UUID) -> SessionResult:
        """Resume a paused session."""

    @abstractmethod
    def close_session(self, session_id: uuid.UUID) -> SessionResult:
        """Close a session; it reaches a terminal state."""

    @abstractmethod
    def get_session(self, session_id: uuid.UUID) -> SessionResult:
        """Look up the current snapshot of a session."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the session backend is ready; never raises."""
