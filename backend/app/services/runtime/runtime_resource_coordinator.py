"""Runtime resource coordinator (Sprint 14.14 — deterministic resource state).

Reasoning-only component that consumes a :class:`RuntimeRecoveryState` and produces
a single immutable, provider-independent :class:`RuntimeResourceState`. It
coordinates runtime resource readiness only: it maps the recovery status to a
resource status and determines whether execution resources are available — but it
never allocates a resource, reserves a resource, executes a capability, performs
planning, or changes the recovery state.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
knowledge, Runtime global, or persistence. Same recovery state in -> same resource
state out. No concrete resources exist yet, so the required-resources set is
always empty (a later sprint introduces real resources).
"""

from typing import Tuple

from app.services.runtime.runtime_recovery_models import RuntimeRecoveryState
from app.services.runtime.runtime_resource_models import (
    ResourceStatus,
    RuntimeResourceState,
)

# Recovery status -> resource status (the mandated deterministic mapping). Any
# unmapped status falls back to READY.
_RECOVERY_TO_RESOURCE = {
    "NOT_REQUIRED": ResourceStatus.READY,
    "READY": ResourceStatus.WAITING,
    "RECOVERING": ResourceStatus.BLOCKED,
    "FAILED": ResourceStatus.BLOCKED,
}

# The resource statuses for which resources are considered ready.
_RESOURCES_READY_STATES = frozenset(
    {ResourceStatus.READY, ResourceStatus.COMPLETED}
)

# No concrete resources exist until Sprint 15, so the required set is always empty.
_REQUIRED_RESOURCES: Tuple[str, ...] = ()


class RuntimeResourceCoordinator:
    """Stateless coordinator: :class:`RuntimeRecoveryState` -> resource state.

    Holds no state and owns no session, provider, cache, clock, or global. It maps
    the recovery status to a resource status, marks resources ready only for a
    ready/completed resource status, and always reports an empty required-resource
    set. It never allocates, reserves, executes, plans, or changes the recovery
    state.
    """

    def create_resource_state(
        self, recovery: RuntimeRecoveryState
    ) -> RuntimeResourceState:
        """Return a deterministic :class:`RuntimeResourceState` (no execution).

        The resource status follows the fixed recovery→resource mapping (an
        unmapped status falls back to ``READY``); ``resources_ready`` is true only
        for a ready/completed resource status; and ``required_resources`` is always
        empty (no concrete resources exist yet). The recovery state is only read —
        never changed — and nothing is allocated, reserved, or executed.
        """
        resource_status = _RECOVERY_TO_RESOURCE.get(
            recovery.recovery_status, ResourceStatus.READY
        )
        resources_ready = resource_status in _RESOURCES_READY_STATES

        return RuntimeResourceState(
            runtime_id=recovery.runtime_id,
            execution_id=recovery.execution_id,
            resource_status=resource_status.value,
            resources_ready=resources_ready,
            required_resources=_REQUIRED_RESOURCES,
            resource_metadata={
                "recovery_status": recovery.recovery_status,
                "resource_status": resource_status.value,
                "resources_ready": resources_ready,
                "required_resource_count": len(_REQUIRED_RESOURCES),
                "recovery_required": recovery.recovery_required,
            },
        )
