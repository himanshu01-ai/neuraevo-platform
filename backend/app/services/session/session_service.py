"""
Session Framework

Stable since Sprint 12.6.

This service is intentionally stateless.

Future functionality should be added
through SessionProvider implementations
rather than modifying this public API.
"""
"""Session Service (Sprint 12.6 — stateless delegator).

Receives lifecycle requests, delegates each to an injected
:class:`SessionProvider`, and returns the provider's result unchanged. That is
its entire responsibility.

It performs NO business logic, retries, caching, persistence, repository access,
runtime, planner, interaction, Gemini, or streaming. The provider is injected via
the constructor (never instantiated here). No concrete provider exists yet — real
session management is a later sprint.
"""

import uuid
from typing import Any, Dict, Optional

from app.services.session.models import SessionResult
from app.services.session.providers.base import SessionProvider


class SessionService:
    """Delegates session lifecycle operations to an injected provider.

    Stateless: it holds only the injected provider and owns no session,
    repository, or cache. A pure pass-through to the provider seam, so provider
    replacement requires no change here.
    """

    def __init__(self, provider: SessionProvider) -> None:
        self.provider = provider

    def create_session(
        self,
        conversation_id: uuid.UUID,
        employee_id: uuid.UUID,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionResult:
        """Delegate session creation to the provider, unchanged."""
        return self.provider.create_session(
            conversation_id, employee_id, metadata
        )

    def pause_session(self, session_id: uuid.UUID) -> SessionResult:
        """Delegate pausing a session to the provider, unchanged."""
        return self.provider.pause_session(session_id)

    def resume_session(self, session_id: uuid.UUID) -> SessionResult:
        """Delegate resuming a session to the provider, unchanged."""
        return self.provider.resume_session(session_id)

    def close_session(self, session_id: uuid.UUID) -> SessionResult:
        """Delegate closing a session to the provider, unchanged."""
        return self.provider.close_session(session_id)

    def get_session(self, session_id: uuid.UUID) -> SessionResult:
        """Delegate looking up a session to the provider, unchanged."""
        return self.provider.get_session(session_id)

    def health_check(self) -> bool:
        """Delegate the backend readiness check to the provider, unchanged."""
        return self.provider.health_check()
