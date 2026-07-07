"""Capability dispatcher models (Sprint 14.4 — immutable dispatch-mapping DTOs).

Provider-independent, immutable mapping of *which capability each ready execution
unit should be routed to*: an ordered list of unit-to-capability assignments, the
unresolved unit ids kept separate, and an overall dispatch status. This DESCRIBES
a routing decision only; it never executes, instantiates a capability, resolves a
provider, or acquires anything — no capability runs here.

Carries only plain data (ids, a label, plain assignment records) — no SDK,
Runtime, Tool, capability, or provider type crosses this boundary. Strictly
additive to Sprints 14.1–14.3, whose modules are left untouched. The DTOs know
nothing about any concrete capability (Browser, Email, Calendar, Python, GitHub,
…): ``capability_name`` is a free-form label.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class CapabilityDispatchStatus(str, Enum):
    """The allowed, deterministic capability-dispatch statuses.

    ``READY`` — every ready unit resolved to a capability. ``PARTIAL`` — some
    ready units resolved, some did not. ``UNRESOLVED`` — nothing could be routed
    (no ready units to route, or none resolved). ``COMPLETED`` — the dispatch plan
    is empty (nothing to route). Kept as a ``str`` enum so each serialises to its
    label.
    """

    READY = "READY"
    PARTIAL = "PARTIAL"
    UNRESOLVED = "UNRESOLVED"
    COMPLETED = "COMPLETED"


class CapabilityAssignment(BaseModel):
    """A single, immutable execution-unit -> capability assignment (no execution).

    ``execution_unit_id`` names the ready unit; ``capability_name`` is the
    free-form label of the capability it is routed to (never an enum of known
    capabilities, keeping the mapping provider-independent). Frozen; this is
    structure only — no capability is instantiated or run.
    """

    model_config = ConfigDict(frozen=True)

    execution_unit_id: str
    capability_name: str


class CapabilityDispatchPlan(BaseModel):
    """Immutable capability routing over a dispatch plan's ready units (no execution).

    ``frozen=True`` makes instances immutable. ``runtime_id`` and ``execution_id``
    link back to the runtime session; ``dispatch_status`` is one of the
    :class:`CapabilityDispatchStatus` labels; ``capability_assignments`` are the
    ordered :class:`CapabilityAssignment` records (preserving the dispatch plan's
    ready-unit order); ``unresolved_execution_units`` are the ready unit ids that
    could not be routed, kept separate; and ``dispatch_metadata`` carries
    provider/telemetry data. This is a routing plan only — it dispatches and
    executes nothing. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    runtime_id: str
    execution_id: str
    dispatch_status: str
    capability_assignments: List[CapabilityAssignment] = Field(
        default_factory=list
    )
    unresolved_execution_units: List[str] = Field(default_factory=list)
    dispatch_metadata: Dict[str, Any] = Field(default_factory=dict)
