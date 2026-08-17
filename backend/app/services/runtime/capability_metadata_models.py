"""Capability metadata models (Sprint 15.3 — immutable capability-metadata DTOs).

Provider-independent, immutable DTOs describing *what each registered capability
can do* and *an immutable snapshot of the whole metadata view*. A
:class:`CapabilityMetadata` enriches one
:class:`~app.services.runtime.capability_registry_models.CapabilityDefinition`
with structured descriptors — the supported actions, required permissions, and
input/output schemas — alongside the definition's identity fields. A
:class:`CapabilityMetadataSnapshot` is an immutable, ordered view of every
capability's metadata with a deterministic count and snapshot descriptors.

These carry only plain data across the boundary; they describe capabilities and
execute nothing — no capability, resolution, discovery, instantiation, dispatch,
network, or SDK lives here, and nothing mutates the registry. Strictly additive to
Sprints 15.1–15.2, whose modules are left untouched. Every field is a free-form
descriptor, so the metadata stays capability-agnostic (Browser, Email, Calendar,
Python, GitHub, CRM, … are all just ids).
"""

from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, ConfigDict, Field


class CapabilityMetadata(BaseModel):
    """Immutable structured metadata describing one capability (no execution).

    ``frozen=True`` makes instances immutable. The identity fields
    (``capability_id``, ``capability_name``, ``capability_description``,
    ``capability_version``, ``capability_category``) mirror the source
    :class:`CapabilityDefinition`. ``supported_actions`` is the immutable tuple of
    actions the capability exposes; ``required_permissions`` is the immutable
    tuple of permissions it needs; ``input_schema``/``output_schema`` describe its
    plain-data I/O shape; and ``metadata`` carries the capability's remaining
    deterministic descriptors. The structured descriptors default to empty when
    the definition carries none. Building this DTO instantiates and executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_id: str
    capability_name: str
    capability_description: str
    capability_version: str
    capability_category: str
    supported_actions: Tuple[str, ...] = Field(default_factory=tuple)
    required_permissions: Tuple[str, ...] = Field(default_factory=tuple)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityMetadataSnapshot(BaseModel):
    """An immutable, ordered snapshot of every capability's metadata.

    ``frozen=True`` makes instances immutable. ``capabilities`` are the
    :class:`CapabilityMetadata` records in deterministic registry-insertion order
    — a fresh list the manager copies out, never a reference to the registry's
    internal collection, so mutating the snapshot can never affect the registry.
    ``capability_count`` is ``len(capabilities)``; and ``metadata`` carries
    deterministic snapshot descriptors only. An empty ``capabilities`` list (with
    ``capability_count`` 0) is a valid empty snapshot. Producing this DTO executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    capabilities: List[CapabilityMetadata] = Field(default_factory=list)
    capability_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
