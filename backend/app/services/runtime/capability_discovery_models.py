"""Capability discovery models (Sprint 15.4 — immutable discovery DTOs).

Provider-independent, immutable request/result shapes for discovering registered
capabilities from their metadata. The request describes *the search criteria* —
an optional category, supported action, and required permission — and the result
describes *what matched*: the discovered :class:`CapabilityMetadata` records (in
metadata insertion order), their count, and metadata.

These carry only plain data across the boundary; they describe a search and
execute nothing — no capability, resolution, instantiation, dispatch, network, or
SDK lives here, and nothing mutates the metadata snapshot. Strictly additive to
Sprints 15.1–15.3, whose modules are left untouched. Every field is a free-form
descriptor, so discovery stays capability-agnostic (Browser, Email, Calendar,
Python, GitHub, CRM, … are all just ids).
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.capability_metadata_models import CapabilityMetadata


class CapabilityDiscoveryRequest(BaseModel):
    """Immutable capability search request (no execution).

    ``frozen=True`` makes instances immutable. Every search field is optional and
    defaults to ``None`` (unset): ``capability_category`` matches a capability's
    exact category; ``supported_action`` requires the capability to expose that
    action; ``required_permission`` requires the capability to declare that
    permission. When every search field is unset the search matches all
    capabilities. ``discovery_metadata`` carries deterministic call-context
    descriptors and defaults to empty. Building this DTO discovers and executes
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_category: Optional[str] = None
    supported_action: Optional[str] = None
    required_permission: Optional[str] = None
    discovery_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityDiscoveryResult(BaseModel):
    """Immutable result of a capability discovery (no execution).

    ``frozen=True`` makes instances immutable. ``discovered_capabilities`` are the
    matching :class:`CapabilityMetadata` records in metadata insertion order — a
    fresh list, never a reference to the snapshot's internal collection.
    ``capability_count`` is ``len(discovered_capabilities)``; and
    ``discovery_metadata`` carries deterministic descriptors only. An empty result
    (with ``capability_count`` 0) is valid. Producing this DTO executes nothing and
    never mutates the metadata snapshot.
    """

    model_config = ConfigDict(frozen=True)

    discovered_capabilities: List[CapabilityMetadata] = Field(default_factory=list)
    capability_count: int = 0
    discovery_metadata: Dict[str, Any] = Field(default_factory=dict)
