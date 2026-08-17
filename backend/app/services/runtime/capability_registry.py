"""Capability registry (Sprint 15.1 — central catalogue of capability definitions).

The single registry of every :class:`CapabilityDefinition` known to the platform,
so a future resolver/orchestrator can ask "what capabilities exist?". It stores
capability *definitions* and nothing else: it never executes, resolves,
instantiates, dispatches, permissions, plans, retries, logs, caches, or imports
SDKs, and it holds no concrete capability. Purely a register / lookup / snapshot
catalogue over the immutable definitions it is given.

Strictly additive to Sprints 14.1–14.15, whose modules are left untouched. It
knows nothing about any concrete capability (Browser, Email, Calendar, Python,
GitHub, CRM, …): a definition is a free-form descriptor keyed by ``capability_id``.
"""

from typing import Dict, List, Optional

from app.services.runtime.capability_registry_models import (
    CapabilityDefinition,
    CapabilityRegistrySnapshot,
)


class CapabilityRegistry:
    """A catalogue of registered capability definitions, keyed by ``capability_id``.

    Holds only ``self._definitions`` — an insertion-ordered map of
    :class:`CapabilityDefinition` records keyed by ``capability_id``. No globals,
    no singleton, no cache. Registering a duplicate ``capability_id`` raises
    ``ValueError``. Definitions are immutable DTOs stored exactly as given and
    never modified. The registry resolves, instantiates, and executes nothing.
    """

    def __init__(
        self, definitions: Optional[List[CapabilityDefinition]] = None
    ) -> None:
        # Build a fresh internal map so the caller's list is never referenced or
        # mutated; register() enforces the unique-``capability_id`` invariant on
        # every entry. Python dicts preserve insertion order, so iteration order
        # is deterministic (insertion order). The initial registry is empty.
        self._definitions: Dict[str, CapabilityDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: CapabilityDefinition) -> None:
        """Register ``definition``; raise ``ValueError`` on a duplicate id.

        The definition (an immutable DTO) is stored unchanged under its
        ``capability_id``. This is the only mutation the registry performs — it
        never touches, resolves, or instantiates a capability.
        """
        if definition.capability_id in self._definitions:
            raise ValueError(
                f"Capability already registered: {definition.capability_id}"
            )
        self._definitions[definition.capability_id] = definition

    def get_capability(self, capability_id: str) -> CapabilityDefinition:
        """Return the registered definition for ``capability_id``.

        Returns the very same immutable :class:`CapabilityDefinition` that was
        registered. Raises ``KeyError`` if none is registered under that id.
        """
        return self._definitions[capability_id]

    def has_capability(self, capability_id: str) -> bool:
        """Return whether a definition is registered under ``capability_id``."""
        return capability_id in self._definitions

    def snapshot(self) -> CapabilityRegistrySnapshot:
        """Return an immutable snapshot of all registered definitions.

        ``capabilities`` is a fresh list built in deterministic insertion order —
        never the registry's internal collection — so mutating the snapshot can
        never affect the registry. ``capability_count`` is the number registered;
        ``registry_metadata`` carries deterministic descriptors only. Producing
        the snapshot resolves and executes nothing.
        """
        definitions = list(self._definitions.values())
        return CapabilityRegistrySnapshot(
            capabilities=definitions,
            capability_count=len(definitions),
            registry_metadata={
                "capability_count": len(definitions),
                "registry_ordering": "insertion",
            },
        )
