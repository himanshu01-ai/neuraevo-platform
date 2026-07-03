"""Permissions package (Sprint 11.3 — permission framework foundation).

Ships ONLY the permission-check framework: the provider-independent
:class:`PermissionRequest` / :class:`PermissionResult` models, the abstract
:class:`PermissionProvider` contract, and the stateless
:class:`PermissionService` delegator. No concrete permission logic, user-approval
flow, HTTP client, SDK, OAuth, planner, or execution — those belong to later
sprints.
"""

from app.services.permissions.models import (
    PermissionRequest,
    PermissionResult,
)
from app.services.permissions.permission_service import PermissionService
from app.services.permissions.providers import PermissionProvider

__all__ = [
    "PermissionService",
    "PermissionProvider",
    "PermissionRequest",
    "PermissionResult",
]
