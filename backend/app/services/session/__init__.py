"""Session package (Sprint 12.6 — session lifecycle framework).

Ships ONLY the lifecycle framework: the provider-independent
:class:`SessionState` / :class:`ConversationSession` / :class:`SessionResult`
models, the abstract :class:`SessionProvider` contract, and the stateless
:class:`SessionService` delegator. It is the lifecycle abstraction future
real-time / Gemini Live / streaming / multimodal / tool-execution sessions will
build on — but it knows nothing about Gemini, audio, streaming, or transport, and
is not wired into the Runtime or AI Orchestrator. No concrete provider, SDK,
networking, streaming, or persistence — those belong to later sprints.
"""

from app.services.session.models import (
    ConversationSession,
    SessionResult,
    SessionState,
)
from app.services.session.providers import SessionProvider
from app.services.session.session_service import SessionService

__all__ = [
    "SessionService",
    "SessionProvider",
    "SessionState",
    "ConversationSession",
    "SessionResult",
]
