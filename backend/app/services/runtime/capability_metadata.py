"""Capability metadata manager (Sprint 15.3 — deterministic metadata snapshots).

Reads a :class:`CapabilityRegistry` and enriches each registered
:class:`CapabilityDefinition` into an immutable :class:`CapabilityMetadata`,
producing a :class:`CapabilityMetadataSnapshot` in registry-insertion order. It
reads the registry only: it never executes, resolves, discovers, or instantiates
capabilities, and it never mutates the registry. Purely a read-and-describe
projection over the registered definitions.

Deterministic and offline: no AI, network, clock, UUID, or SDK. Same registry
contents -> identical snapshot. Strictly additive to Sprints 15.1–15.2, whose
modules are left untouched; it knows nothing about any concrete capability
(Browser, Email, Calendar, Python, GitHub, CRM, …).
"""

from typing import List

from app.services.runtime.capability_registry import CapabilityRegistry
from app.services.runtime.capability_registry_models import CapabilityDefinition
from app.services.runtime.capability_metadata_models import (
    CapabilityMetadata,
    CapabilityMetadataSnapshot,
)


class CapabilityMetadataManager:
    """Manager: (:class:`CapabilityRegistry`) -> capability metadata snapshot.

    Stateless beyond the injected :class:`CapabilityRegistry` reference — it owns
    no session, cache, clock, or mutable state. ``snapshot`` reads the registry's
    registered definitions (insertion order preserved), maps each to exactly one
    immutable :class:`CapabilityMetadata`, and returns an immutable
    :class:`CapabilityMetadataSnapshot`. It reads the registry only — it never
    registers, resolves, executes, instantiates, or mutates anything.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def snapshot(self) -> CapabilityMetadataSnapshot:
        """Return an immutable :class:`CapabilityMetadataSnapshot` (read-only).

        Reads the registry's definitions in insertion order (via the registry's
        own read-only snapshot), maps each :class:`CapabilityDefinition` to exactly
        one :class:`CapabilityMetadata`, and builds a fresh, copied-out list — never
        the registry's internal collection. ``metadata`` carries deterministic
        snapshot descriptors only. The registry is only read — never mutated — and
        nothing is executed or instantiated.
        """
        definitions = self.registry.snapshot().capabilities
        metadata: List[CapabilityMetadata] = [
            self._describe(definition) for definition in definitions
        ]
        return CapabilityMetadataSnapshot(
            capabilities=metadata,
            capability_count=len(metadata),
            metadata={
                "capability_count": len(metadata),
                "metadata_ordering": "insertion",
            },
        )

    @staticmethod
    def _describe(definition: CapabilityDefinition) -> CapabilityMetadata:
        """Map one :class:`CapabilityDefinition` to its :class:`CapabilityMetadata`.

        The identity fields are copied directly. The structured descriptors are
        read from the definition's ``capability_metadata`` when present and fall
        back to the empty defaults (``()``/``{}``) otherwise; ``metadata`` carries
        the definition's own descriptors unchanged. This is a pure, deterministic
        projection — it reads the definition only and mutates nothing.
        """
        source = definition.capability_metadata
        return CapabilityMetadata(
            capability_id=definition.capability_id,
            capability_name=definition.capability_name,
            capability_description=definition.capability_description,
            capability_version=definition.capability_version,
            capability_category=definition.capability_category,
            supported_actions=source.get("supported_actions", ()),
            required_permissions=source.get("required_permissions", ()),
            input_schema=source.get("input_schema", {}),
            output_schema=source.get("output_schema", {}),
            metadata=source,
        )
