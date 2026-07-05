"""Session providers package (Sprint 12.6 — abstraction only).

Exposes the abstract :class:`SessionProvider` contract. No concrete session
provider is implemented in this sprint — only the interface future sprints will
implement.
"""

from app.services.session.providers.base import SessionProvider

__all__ = ["SessionProvider"]
