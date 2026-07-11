"""Capability router (Sprint 15.15 — resolve, validate, dispatch).

Defines :class:`CapabilityRouter`, the component that maps a capability name to a
concrete Sprint 14.3 :class:`ExecutionCapability` and dispatches a
:class:`CapabilityExecutionRequest` to it. It resolves a capability, validates its
availability, and dispatches — nothing else: no planning, no workflow ordering, no
output threading (that is the coordinator's job).

The router is constructed with an injected name→capability mapping (dependency
injection at the composition root); it holds no static or singleton state and never
instantiates a capability itself. Because it only knows the
:class:`ExecutionCapability` contract, any provider implementation plugs in behind a
name without the router changing — and no provider/SDK object is ever exposed, only
the plain :class:`CapabilityExecutionResult` the capability returns. Strictly additive
to Sprints 15.1–15.14.
"""

from typing import Dict, List, Mapping

from app.services.runtime.execution_capability import ExecutionCapability
from app.services.runtime.execution_capability_models import (
    CapabilityExecutionRequest,
    CapabilityExecutionResult,
)
from app.services.runtime.workflow_models import CapabilityUnavailableError


class CapabilityRouter:
    """Resolves capability names to capabilities and dispatches requests to them.

    Holds an immutable copy of the injected name→:class:`ExecutionCapability` mapping.
    ``is_available``/``available_capabilities`` report the registry; ``resolve``
    returns the capability (raising :class:`CapabilityUnavailableError` when unknown);
    ``dispatch`` resolves then executes through the :class:`ExecutionCapability`
    contract. It performs no workflow ordering and exposes no provider object.
    """

    def __init__(self, capabilities: Mapping[str, ExecutionCapability]) -> None:
        self._capabilities: Dict[str, ExecutionCapability] = dict(capabilities)

    def is_available(self, capability_name: str) -> bool:
        """Return whether ``capability_name`` resolves to a registered capability."""
        return capability_name in self._capabilities

    def available_capabilities(self) -> List[str]:
        """Return the registered capability names, sorted deterministically."""
        return sorted(self._capabilities)

    def resolve(self, capability_name: str) -> ExecutionCapability:
        """Return the capability for ``capability_name`` or raise if unavailable.

        Raises :class:`CapabilityUnavailableError` (a deterministic workflow error)
        when the name is not registered; the coordinator catches it and reports a
        graceful ``FAILED`` result.
        """
        capability = self._capabilities.get(capability_name)
        if capability is None:
            raise CapabilityUnavailableError(
                f"capability unavailable: {capability_name}"
            )
        return capability

    def dispatch(
        self, request: CapabilityExecutionRequest
    ) -> CapabilityExecutionResult:
        """Resolve the request's capability and execute it via the contract.

        Returns the capability's plain :class:`CapabilityExecutionResult`. Raises
        :class:`CapabilityUnavailableError` if the capability is not registered — it
        never lets a provider/SDK object escape.
        """
        capability = self.resolve(request.capability_name)
        return capability.execute(request)
