"""Capability registry models (Sprint 15.1 — immutable capability-catalogue DTOs).

Provider-independent, immutable DTOs describing *the capabilities known to the
platform* and *an immutable snapshot of the whole registry*. A
:class:`CapabilityDefinition` is a plain-data description of one capability (a
stable id, a name, a description, a version, a category, and metadata) — never a
capability instance, provider, or SDK object. A
:class:`CapabilityRegistrySnapshot` is an immutable, ordered view of every
registered definition with a deterministic count and registry descriptors.

These carry only plain data across the boundary; they describe capabilities and
execute nothing — no capability, resolution, instantiation, dispatch, network, or
SDK lives here. Strictly additive to Sprints 14.1–14.15, whose modules are left
untouched. The DTOs know nothing about any concrete capability (Browser, Email,
Calendar, Python, GitHub, CRM, …): every field is a free-form descriptor, so the
catalogue stays capability-agnostic.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class CapabilityDefinition(BaseModel):
    """An immutable, provider-independent definition of a single capability.

    ``frozen=True`` makes instances immutable, so a definition cannot be mutated
    after it is registered. ``capability_id`` is the unique, stable identifier the
    registry keys on; ``capability_name`` is a human-facing label;
    ``capability_description`` explains the capability in plain language;
    ``capability_version`` is a free-form version descriptor;
    ``capability_category`` groups related capabilities; and
    ``capability_metadata`` carries deterministic descriptors (never a
    provider/SDK object). This is a description only — building it instantiates
    and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_id: str
    capability_name: str
    capability_description: str
    capability_version: str
    capability_category: str
    capability_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityRegistrySnapshot(BaseModel):
    """An immutable, ordered snapshot of the whole capability registry.

    ``frozen=True`` makes instances immutable. ``capabilities`` are the registered
    :class:`CapabilityDefinition` records in deterministic insertion order — a
    fresh list the registry copies out, never a reference to its internal
    collection, so mutating the snapshot can never affect the registry.
    ``capability_count`` is ``len(capabilities)``; and ``registry_metadata``
    carries deterministic registry descriptors only. An empty ``capabilities``
    list (with ``capability_count`` 0) is a valid empty registry. Producing this
    DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    capabilities: List[CapabilityDefinition] = Field(default_factory=list)
    capability_count: int = 0
    registry_metadata: Dict[str, Any] = Field(default_factory=dict)
