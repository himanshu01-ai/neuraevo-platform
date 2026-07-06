"""Execution preparation engine (Sprint 13.3 — deterministic capability mapping).

Reasoning-only component that inspects an :class:`ExecutionPlan` and produces an
:class:`ExecutionPreparation`: the capabilities, external services, and
permissions the plan would eventually require, its step count, whether it could
start immediately, what blocks it, and which execution strategy fits.

It is PREPARATION ONLY and fully deterministic and offline. It does NOT execute
tools, call the Runtime, Planner framework, Registry, Permission service, or Tool
execution; and it uses no AI, SDK, network, memory, or persistence. Same plan in
-> same preparation out.
"""

from typing import Dict, List, Tuple

from app.services.planning.execution_preparation_models import (
    ExecutionPreparation,
    ExecutionStrategy,
)
from app.services.planning.models import ExecutionPlan

# Category -> ordered high-level capabilities the plan would require.
_CATEGORY_CAPABILITIES: Dict[str, Tuple[str, ...]] = {
    "travel": ("Calendar", "Maps", "Email", "Browser"),
    "interview": ("Browser", "Documents"),
    "fitness": ("Documents", "Calendar"),
    "business": ("Browser", "Documents", "Spreadsheet"),
    "study": ("Browser", "Documents"),
    "scheduling": ("Calendar", "Reminder", "Notifications"),
}

# Category -> deterministic execution strategy (never guessed).
_CATEGORY_STRATEGY: Dict[str, str] = {
    "travel": ExecutionStrategy.SEQUENTIAL.value,
    "interview": ExecutionStrategy.SEQUENTIAL.value,
    "fitness": ExecutionStrategy.HYBRID.value,
    "business": ExecutionStrategy.PARALLEL.value,
    "study": ExecutionStrategy.SEQUENTIAL.value,
    "scheduling": ExecutionStrategy.SEQUENTIAL.value,
}

# Capability -> the permission its use would require (omitted => read-only).
_CAPABILITY_PERMISSIONS: Dict[str, str] = {
    "Calendar": "Calendar Write",
    "Email": "Email Send",
    "Maps": "Location",
    "Reminder": "Reminder Write",
    "Notifications": "Notification Send",
    "Spreadsheet": "File Write",
}

# Capability -> the external service it connects to.
_CAPABILITY_SERVICES: Dict[str, str] = {
    "Calendar": "Calendar Service",
    "Email": "Email Service",
    "Maps": "Maps Service",
    "Browser": "Web",
    "Documents": "Document Storage",
    "Spreadsheet": "Spreadsheet Service",
    "Reminder": "Reminder Service",
    "Notifications": "Notification Service",
}

# External services that require the user to own/link an account.
_ACCOUNT_SERVICES = frozenset({"Calendar Service", "Email Service"})


class ExecutionPreparationEngine:
    """Stateless preparer: :class:`ExecutionPlan` -> :class:`ExecutionPreparation`.

    Holds no state and owns no session, provider, or cache. It maps the plan's
    goal category to the capabilities/permissions/services it would require,
    picks a deterministic strategy, counts steps, and derives the blockers that
    would prevent immediate execution — all by reading the plan only. It never
    executes anything.
    """

    def prepare(self, plan: ExecutionPlan) -> ExecutionPreparation:
        """Return a deterministic :class:`ExecutionPreparation` for ``plan``.

        Capabilities/permissions/services and strategy come from the plan's goal
        category (falling back to no capabilities and a sequential strategy when
        unknown). Blockers are derived from the plan's own missing information and
        confirmation intent plus the required permissions/services. The plan is
        only read — never mutated — and nothing is executed.
        """
        category = self._category(plan)
        capabilities = list(_CATEGORY_CAPABILITIES.get(category, ()))
        permissions = self._map(capabilities, _CAPABILITY_PERMISSIONS)
        services = self._map(capabilities, _CAPABILITY_SERVICES)
        strategy = _CATEGORY_STRATEGY.get(
            category, ExecutionStrategy.SEQUENTIAL.value
        )
        blockers = self._blockers(plan, permissions, services)

        return ExecutionPreparation(
            required_capabilities=capabilities,
            external_services=services,
            permissions_required=permissions,
            estimated_execution_steps=len(plan.steps),
            can_execute_immediately=not blockers,
            blocked_by=blockers,
            execution_strategy=strategy,
        )

    @staticmethod
    def _category(plan: ExecutionPlan) -> str:
        """Read the plan's goal category from metadata (``""`` when absent)."""
        value = plan.metadata.get("category", "") if plan.metadata else ""
        return value if isinstance(value, str) else ""

    @staticmethod
    def _map(capabilities: List[str], mapping: Dict[str, str]) -> List[str]:
        """Map capabilities through ``mapping``, order-preserving and de-duped."""
        result: List[str] = []
        for capability in capabilities:
            value = mapping.get(capability)
            if value and value not in result:
                result.append(value)
        return result

    @staticmethod
    def _blockers(
        plan: ExecutionPlan, permissions: List[str], services: List[str]
    ) -> List[str]:
        """Derive the deterministic, ordered, non-empty list of blockers."""
        blockers: List[str] = []
        if plan.missing_information:
            blockers.append("Need Missing Information")
        if permissions:
            blockers.append("Need Permission")
        if services:
            blockers.append("Need Authentication")
        if any(service in _ACCOUNT_SERVICES for service in services):
            blockers.append("Need External Account")
        if plan.requires_user_confirmation:
            blockers.append("Need User Approval")
        return blockers
