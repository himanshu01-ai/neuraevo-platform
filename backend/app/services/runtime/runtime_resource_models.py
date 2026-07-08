"""Runtime resource models (Sprint 14.14 — immutable resource-state DTOs).

Provider-independent, immutable statement of *whether the runtime's execution
resources are ready*: a resource status, a readiness flag, and the (currently
empty) required resources. This COORDINATES resource readiness only; the state
object allocates, reserves, and executes nothing — it is derived from a recovery
snapshot. No concrete resources exist yet, so ``required_resources`` is always an
empty tuple until Sprint 15.

Carries only plain data (ids, a label, a bool, an empty tuple) — no SDK, Runtime,
Tool, capability, or provider type crosses this boundary. Strictly additive to
Sprints 14.1–14.13, whose modules are left untouched. It knows nothing about any
concrete capability or resource.
"""

from enum import Enum
from typing import Any, Dict, Tuple

from pydantic import BaseModel, ConfigDict, Field


class ResourceStatus(str, Enum):
    """The allowed, deterministic runtime resource statuses.

    ``READY`` — resources are available. ``WAITING`` — waiting on recovery before
    resources apply. ``BLOCKED`` — resources cannot be readied. ``COMPLETED`` —
    resources are no longer needed. Kept as a ``str`` enum so each serialises to
    its label.
    """

    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class RuntimeResourceState(BaseModel):
    """Immutable runtime resource readiness state (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``resource_status`` is one of the
    :class:`ResourceStatus` labels; ``resources_ready`` marks whether execution
    resources are available; ``required_resources`` is the (currently always
    empty) tuple of required resources — no concrete resources exist until Sprint
    15; and ``resource_metadata`` carries deterministic state descriptors. This is
    a readiness snapshot only — it allocates, reserves, and runs nothing.
    Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    resource_status: str
    resources_ready: bool
    required_resources: Tuple[str, ...] = Field(default_factory=tuple)
    resource_metadata: Dict[str, Any] = Field(default_factory=dict)
