"""Capability resolver models (Sprint 15.2 — immutable resolution DTOs).

Provider-independent, immutable request/result shapes for resolving a single
registered capability by ``capability_id`` against a
:class:`~app.services.runtime.capability_registry.CapabilityRegistry`. The request
describes *which capability to look up*; the result describes *what the lookup
found* — a found flag, the exact registered
:class:`~app.services.runtime.capability_registry_models.CapabilityDefinition`
(or ``None``), a status label, and metadata.

These carry only plain data across the boundary; they describe a resolution and
execute nothing — no capability, instantiation, dispatch, AI reasoning, network,
or SDK lives here, and nothing mutates the registry. Strictly additive to Sprint
15.1, whose modules are left untouched. Every field is a free-form descriptor, so
resolution stays capability-agnostic (Browser, Email, Calendar, Python, GitHub,
CRM, … are all just ids).
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.runtime.capability_registry_models import CapabilityDefinition


class ResolutionStatus(str, Enum):
    """The allowed, deterministic capability-resolution statuses.

    ``FOUND`` — a definition is registered under the requested ``capability_id``.
    ``NOT_FOUND`` — none is. Kept as a ``str`` enum so each serialises to its
    label. These are outcome labels only; no status here causes anything to run.
    """

    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"


class CapabilityResolutionRequest(BaseModel):
    """Immutable request to resolve one capability by id (no execution).

    ``frozen=True`` makes instances immutable. ``capability_id`` is the id to look
    up in the registry; ``resolution_metadata`` carries deterministic call-context
    descriptors (never a provider/SDK object) and defaults to empty so callers may
    omit it. Building this DTO resolves and executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    capability_id: str
    resolution_metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityResolutionResult(BaseModel):
    """Immutable result of resolving one capability (no execution).

    ``frozen=True`` makes instances immutable. ``capability_found`` is ``True``
    only when a definition was registered under the requested id;
    ``capability_definition`` is the exact registered
    :class:`CapabilityDefinition` when found and ``None`` otherwise;
    ``resolution_status`` is one of the :class:`ResolutionStatus` labels; and
    ``resolution_metadata`` carries deterministic descriptors only. This is a
    reported outcome shape; producing it executes nothing and never mutates the
    registry.
    """

    model_config = ConfigDict(frozen=True)

    capability_found: bool
    capability_definition: Optional[CapabilityDefinition] = None
    resolution_status: str
    resolution_metadata: Dict[str, Any] = Field(default_factory=dict)
