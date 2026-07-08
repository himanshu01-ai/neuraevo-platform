"""Capability resolver (Sprint 15.2 — deterministic capability resolution).

Consumes a :class:`CapabilityRegistry` and a :class:`CapabilityResolutionRequest`
and deterministically resolves the registered capability by ``capability_id``,
returning a :class:`CapabilityResolutionResult`. It reads the registry only: it
never executes, instantiates, dispatches, or performs AI reasoning, and it never
mutates the registry. Purely a lookup that reports the exact registered
:class:`CapabilityDefinition` (or ``None``).

Deterministic and offline: no AI, network, clock, UUID, or SDK. Same registry
contents plus the same request -> identical result. Strictly additive to Sprint
15.1, whose modules are left untouched; it knows nothing about any concrete
capability (Browser, Email, Calendar, Python, GitHub, CRM, …).
"""

from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_resolver_models import (
    CapabilityResolutionRequest,
    CapabilityResolutionResult,
    ResolutionStatus,
)


class CapabilityResolver:
    """Resolver: (:class:`CapabilityResolutionRequest`) -> resolution result.

    Stateless beyond the injected :class:`CapabilityRegistry` reference — it owns
    no session, cache, clock, or mutable state. ``resolve`` looks the request's
    ``capability_id`` up in the registry and reports the outcome: ``FOUND`` with
    the exact registered :class:`CapabilityDefinition`, or ``NOT_FOUND`` with
    ``None``. It reads the registry only — it never registers, executes,
    instantiates, or mutates anything.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def resolve(
        self, request: CapabilityResolutionRequest
    ) -> CapabilityResolutionResult:
        """Return a deterministic :class:`CapabilityResolutionResult` (read-only).

        When a definition is registered under ``request.capability_id`` the result
        is ``FOUND`` and carries the exact registered
        :class:`CapabilityDefinition`; otherwise it is ``NOT_FOUND`` with
        ``capability_definition`` set to ``None``. The registry is only read —
        never mutated — and nothing is executed or instantiated.
        """
        if self.registry.has_capability(request.capability_id):
            definition = self.registry.get_capability(request.capability_id)
            return self._result(request, ResolutionStatus.FOUND, definition)
        return self._result(request, ResolutionStatus.NOT_FOUND, None)

    @staticmethod
    def _result(
        request: CapabilityResolutionRequest,
        status: ResolutionStatus,
        definition,
    ) -> CapabilityResolutionResult:
        """Build the immutable result with deterministic resolution descriptors."""
        return CapabilityResolutionResult(
            capability_found=status is ResolutionStatus.FOUND,
            capability_definition=definition,
            resolution_status=status.value,
            resolution_metadata={
                "capability_id": request.capability_id,
                "resolution_status": status.value,
            },
        )
