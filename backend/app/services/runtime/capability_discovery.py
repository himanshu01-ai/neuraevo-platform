"""Capability discovery manager (Sprint 15.4 — deterministic capability discovery).

Consumes the :class:`CapabilityMetadataSnapshot` produced by an injected
:class:`CapabilityMetadataManager` and deterministically discovers the
capabilities matching a :class:`CapabilityDiscoveryRequest`, returning a
:class:`CapabilityDiscoveryResult`. It reads metadata only: it never executes,
resolves, or instantiates capabilities, and it never mutates the metadata
snapshot or the registry behind it. Purely a deterministic filter over the
metadata.

Deterministic and offline: no AI, network, clock, UUID, or SDK. Same metadata plus
the same request -> identical result. Strictly additive to Sprints 15.1–15.3,
whose modules are left untouched; it knows nothing about any concrete capability
(Browser, Email, Calendar, Python, GitHub, CRM, …).
"""

from typing import List

from app.services.runtime.capability_discovery_models import (
    CapabilityDiscoveryRequest,
    CapabilityDiscoveryResult,
)
from app.services.runtime.capability_metadata import CapabilityMetadataManager
from app.services.runtime.capability_metadata_models import CapabilityMetadata


class CapabilityDiscoveryManager:
    """Discovery: (:class:`CapabilityDiscoveryRequest`) -> discovery result.

    Stateless beyond the injected :class:`CapabilityMetadataManager` reference — it
    owns no session, cache, clock, or mutable state. ``discover`` reads the
    manager's metadata snapshot, keeps the capabilities matching every supplied
    filter (metadata insertion order preserved), and returns an immutable
    :class:`CapabilityDiscoveryResult` with a fresh list. It reads metadata only —
    it never registers, resolves, executes, instantiates, or mutates anything.
    """

    def __init__(self, metadata_manager: CapabilityMetadataManager) -> None:
        self.metadata_manager = metadata_manager

    def discover(
        self, request: CapabilityDiscoveryRequest
    ) -> CapabilityDiscoveryResult:
        """Return a deterministic :class:`CapabilityDiscoveryResult` (read-only).

        Reads the metadata snapshot and keeps every capability that matches all
        supplied filters — an unset filter is ignored, so a fully-empty request
        matches everything. Matching preserves the snapshot's insertion order and
        builds a fresh list; the snapshot is only read — never mutated — and
        nothing is executed.
        """
        capabilities = self.metadata_manager.snapshot().capabilities
        discovered: List[CapabilityMetadata] = [
            metadata
            for metadata in capabilities
            if self._matches(metadata, request)
        ]
        return CapabilityDiscoveryResult(
            discovered_capabilities=discovered,
            capability_count=len(discovered),
            discovery_metadata={
                "capability_count": len(discovered),
                "total_capabilities": len(capabilities),
                "discovery_ordering": "insertion",
            },
        )

    @staticmethod
    def _matches(
        metadata: CapabilityMetadata, request: CapabilityDiscoveryRequest
    ) -> bool:
        """Return whether ``metadata`` satisfies every supplied filter.

        Each filter is applied only when supplied (a truthy field): the category
        must match exactly, the supported action must be present in the
        capability's actions, and the required permission must be present in its
        permissions. All supplied filters must match (intersection); an unset
        filter is skipped, so an all-unset request matches every capability.
        """
        if (
            request.capability_category
            and metadata.capability_category != request.capability_category
        ):
            return False
        if (
            request.supported_action
            and request.supported_action not in metadata.supported_actions
        ):
            return False
        if (
            request.required_permission
            and request.required_permission not in metadata.required_permissions
        ):
            return False
        return True
