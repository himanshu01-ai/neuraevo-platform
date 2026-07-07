"""Execution capability contract (Sprint 14.3 — provider-independent seam).

Defines the replaceable interface that every future capability (Browser, Email,
Calendar, Python, GitHub, CRM, …) must implement to run a single execution unit
and report a result. Concrete capabilities live behind this interface so the rest
of the runtime stays capability-agnostic: it knows the contract, never the
capability.

This sprint ships ONLY the contract — no concrete capability, no dispatch, no
execution. A capability turns a :class:`CapabilityExecutionRequest` into a
:class:`CapabilityExecutionResult`; the interface itself performs no execution,
networking, SDK work, registry lookup, or runtime coordination, holds no state,
and contains no business logic.
"""

from abc import ABC, abstractmethod

from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
)


class ExecutionCapability(ABC):
    """Replaceable, provider-independent contract for executing one unit.

    ``execute`` turns a :class:`CapabilityExecutionRequest` into a
    :class:`CapabilityExecutionResult`. Implementations own all capability logic
    behind this interface; they must remain stateless and must never expose a
    provider/SDK object across this boundary. The interface knows nothing about
    any concrete capability and defines only the execution contract — it holds no
    state, no registry, and no business logic.
    """

    @abstractmethod
    def execute(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Return a :class:`CapabilityExecutionResult` for ``request``.

        The contract: a capability acts on the single execution unit named in the
        request and reports a result carrying its status and outputs. This is the
        interface only — no concrete execution, networking, or SDK work is defined
        here; a later sprint supplies real capabilities behind it.
        """
