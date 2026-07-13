"""Authorization manager (Sprint 16.11 — deterministic, local authorization).

Defines the :class:`AuthorizationManager` abstraction and its default
:class:`LocalAuthorizationManager`, a deterministic, local, in-memory authorization
policy. A manager answers ``authorize`` (an action for a principal on a resource),
``validate_permission`` (does a principal hold a permission), and ``validate_role``
(does a principal hold a role). The default resolves a principal's permissions from
its roles and matches them against the permission an action requires.

This is an authorization *abstraction* only — it performs no authentication, no
OAuth, no SSO/LDAP, and talks to no identity provider. It is deterministic and
stateless and decides only: it delegates nothing and executes nothing. Strictly
additive to Sprints 1.x–16.10, whose modules are left untouched.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Set

from app.services.ai_employee.operations.models import (
    AuthorizationDecision,
    AuthorizationResult,
)

# The wildcard permission that grants every action.
_WILDCARD = "*"


class AuthorizationManager(ABC):
    """Abstraction that decides whether a principal may perform an action (no auth).

    An implementation answers ``authorize`` (returning an
    :class:`AuthorizationResult`), ``validate_permission``, and ``validate_role``.
    Implementations must be deterministic and must not authenticate, call an identity
    provider, or execute anything.
    """

    @abstractmethod
    def authorize(
        self, principal: str, action: str, resource: str = ""
    ) -> AuthorizationResult:
        """Return the :class:`AuthorizationResult` for ``principal``/``action``."""

    @abstractmethod
    def validate_permission(self, principal: str, permission: str) -> bool:
        """Return whether ``principal`` holds ``permission``."""

    @abstractmethod
    def validate_role(self, principal: str, role: str) -> bool:
        """Return whether ``principal`` holds ``role``."""


class LocalAuthorizationManager(AuthorizationManager):
    """Deterministic, local authorization over an in-memory role/permission policy.

    Constructed with ``role_bindings`` (principal -> roles), ``role_permissions``
    (role -> permissions), ``action_permissions`` (action -> the required
    permission), and ``default_allow`` (the decision for an action with no required
    permission; defaults to ``False`` — deny by default). A principal holding the
    ``"*"`` permission is allowed every action. It authenticates nothing, calls no
    identity provider, and is deterministic and stateless.
    """

    def __init__(
        self,
        role_bindings: Optional[Dict[str, Set[str]]] = None,
        role_permissions: Optional[Dict[str, Set[str]]] = None,
        action_permissions: Optional[Dict[str, str]] = None,
        default_allow: bool = False,
    ) -> None:
        self._role_bindings = {
            principal: set(roles)
            for principal, roles in (role_bindings or {}).items()
        }
        self._role_permissions = {
            role: set(permissions)
            for role, permissions in (role_permissions or {}).items()
        }
        self._action_permissions = dict(action_permissions or {})
        self._default_allow = default_allow

    def authorize(
        self, principal: str, action: str, resource: str = ""
    ) -> AuthorizationResult:
        """Return the deterministic authorization decision for the request."""
        permissions = self._permissions_for(principal)
        required = self._action_permissions.get(action)
        if _WILDCARD in permissions:
            allowed, reason = True, "wildcard permission"
        elif required is None:
            allowed = self._default_allow
            reason = (
                "no permission mapping; default "
                f"{'allow' if self._default_allow else 'deny'}"
            )
        else:
            allowed = required in permissions
            reason = f"requires permission {required!r}"
        return AuthorizationResult(
            allowed=allowed,
            decision=(
                AuthorizationDecision.ALLOW
                if allowed
                else AuthorizationDecision.DENY
            ),
            principal=principal,
            action=action,
            resource=resource,
            reason=reason,
        )

    def validate_permission(self, principal: str, permission: str) -> bool:
        """Return whether ``principal`` holds ``permission`` (``"*"`` grants all)."""
        permissions = self._permissions_for(principal)
        return _WILDCARD in permissions or permission in permissions

    def validate_role(self, principal: str, role: str) -> bool:
        """Return whether ``principal`` is bound to ``role``."""
        return role in self._role_bindings.get(principal, set())

    # --- helpers ---------------------------------------------------------
    def _permissions_for(self, principal: str) -> Set[str]:
        """Return the union of permissions granted by ``principal``'s roles."""
        permissions: Set[str] = set()
        for role in self._role_bindings.get(principal, set()):
            permissions |= self._role_permissions.get(role, set())
        return permissions
