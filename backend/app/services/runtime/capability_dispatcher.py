"""Capability dispatcher (Sprint 14.4 — deterministic capability routing).

Reasoning-only component that consumes a :class:`DispatchPlan` and determines
which capability each ready execution unit should be routed to, producing a
single immutable, provider-independent :class:`CapabilityDispatchPlan`. It maps
each ready unit id to a capability name, keeps unresolved units separate, and
derives an overall status — but it never executes, instantiates a capability,
performs networking, or acquires anything, and it never mutates the dispatch plan.

Because the dispatch plan carries only unit ids (no capability information) and
this dispatcher must know no concrete capability, resolution is a pure,
deterministic, provider-independent function of the unit id: each non-empty ready
unit resolves to a stable capability *key* derived from its id (a placeholder — a
later sprint, with real capability metadata or a registry, maps these keys to
concrete capabilities), while a blank unit id cannot be resolved. It knows nothing
about Browser, Email, Calendar, Python, GitHub, or any other capability.

Fully deterministic and offline: no AI, network, clock, UUID, SDK, capability
instantiation, registry, Runtime global, or persistence. Same dispatch plan in ->
same capability dispatch plan out.
"""

from typing import List, Optional

from app.services.runtime.capability_dispatcher_models import (
    CapabilityAssignment,
    CapabilityDispatchPlan,
    CapabilityDispatchStatus,
)
from app.services.runtime.task_dispatcher_models import DispatchPlan

# Prefix for the deterministic, provider-independent capability key derived from
# a ready unit id. This is a routing placeholder, never a concrete capability.
_CAPABILITY_KEY_PREFIX = "capability-"


class CapabilityDispatcher:
    """Stateless dispatcher: :class:`DispatchPlan` -> capability routing.

    Holds no state and owns no session, provider, cache, clock, registry, or
    global. It routes each ready unit (in the dispatch plan's exact order) to a
    deterministic capability key, keeps unresolvable units separate, and derives
    the overall status — ready when all ready units resolved, partial when only
    some did, unresolved when none could be routed, and completed for an empty
    plan. It never executes, instantiates a capability, or mutates the dispatch
    plan.
    """

    def create_capability_dispatch_plan(
        self, dispatch_plan: DispatchPlan
    ) -> CapabilityDispatchPlan:
        """Return a deterministic :class:`CapabilityDispatchPlan` (no execution).

        Each ready unit id is resolved, in order, to a capability assignment;
        unit ids that cannot be resolved are kept separate. The status follows a
        fixed rule: an empty plan is completed, no ready units is unresolved, all
        ready units resolved is ready, and a mix is partial. The dispatch plan is
        only read — never mutated — and nothing is executed or dispatched.
        """
        assignments: List[CapabilityAssignment] = []
        unresolved: List[str] = []
        for unit_id in dispatch_plan.ready_execution_units:
            capability_name = self._resolve(unit_id)
            if capability_name is None:
                unresolved.append(unit_id)
            else:
                assignments.append(
                    CapabilityAssignment(
                        execution_unit_id=unit_id,
                        capability_name=capability_name,
                    )
                )

        status = self._status(dispatch_plan, assignments, unresolved)

        return CapabilityDispatchPlan(
            runtime_id=dispatch_plan.runtime_id,
            execution_id=dispatch_plan.execution_id,
            dispatch_status=status.value,
            capability_assignments=assignments,
            unresolved_execution_units=unresolved,
            dispatch_metadata={
                "ready_count": len(dispatch_plan.ready_execution_units),
                "assigned_count": len(assignments),
                "unresolved_count": len(unresolved),
                "source_dispatch_status": dispatch_plan.dispatch_status,
            },
        )

    @staticmethod
    def _resolve(unit_id: str) -> Optional[str]:
        """Resolve a ready unit id to a capability key, or ``None`` if blank.

        Deterministic and provider-independent: a non-empty unit id yields a
        stable capability key derived from it; a blank id cannot be routed.
        """
        if not unit_id.strip():
            return None
        return f"{_CAPABILITY_KEY_PREFIX}{unit_id}"

    @staticmethod
    def _status(
        dispatch_plan: DispatchPlan,
        assignments: List[CapabilityAssignment],
        unresolved: List[str],
    ) -> CapabilityDispatchStatus:
        """Derive the dispatch status by fixed, deterministic precedence.

        No ready units means completed for an empty plan (nothing anywhere) or
        unresolved when other work remains; otherwise all ready units resolved is
        ready, a mix is partial, and none resolved is unresolved.
        """
        if not dispatch_plan.ready_execution_units:
            has_pending = bool(
                dispatch_plan.blocked_execution_units
                or dispatch_plan.deferred_execution_units
            )
            return (
                CapabilityDispatchStatus.UNRESOLVED
                if has_pending
                else CapabilityDispatchStatus.COMPLETED
            )
        if not unresolved:
            return CapabilityDispatchStatus.READY
        if assignments:
            return CapabilityDispatchStatus.PARTIAL
        return CapabilityDispatchStatus.UNRESOLVED
