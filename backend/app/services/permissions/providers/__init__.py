"""Permission providers package (Sprint 11.3 — abstraction only).

Exposes the abstract :class:`PermissionProvider` contract. No concrete
permission provider is implemented in this sprint — only the interface future
sprints will implement.
"""

from app.services.permissions.providers.base import PermissionProvider

__all__ = ["PermissionProvider"]
