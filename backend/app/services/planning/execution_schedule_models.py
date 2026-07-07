"""Execution schedule models (Sprint 13.11 — immutable schedule DTOs).

Provider-independent, immutable statement of *what could run next*: the nodes
selected to run, the ready nodes deferred by ordering, the still-blocked nodes,
a deterministic execution order, and the scheduling strategy. This determines
what COULD run; it never executes, resolves, or acquires anything — no execution
layer exists.

Carries only plain data (ids, ints, bools, plain string lists, nested plain node
records) — no SDK, Runtime, Tool, or Planner-framework type crosses this
boundary. Strictly additive to Sprints 13.1–13.10, whose modules are left
untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class SchedulingStrategy(str, Enum):
    """The allowed, deterministic scheduling strategies.

    ``SEQUENTIAL`` schedules one ready node at a time; ``PARALLEL`` schedules all
    ready nodes at once; ``HYBRID`` schedules a batch and defers the rest. Kept as
    a ``str`` enum so each serialises to its label.
    """

    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    HYBRID = "HYBRID"


class ScheduledNode(BaseModel):
    """A single, immutable scheduled node (no execution).

    ``node_id`` is the graph node; ``execution_unit_id`` links to the queue unit;
    ``priority`` orders scheduled nodes (lower runs first); ``scheduled`` marks
    the node as selected to run; ``reason`` explains the decision in plain
    language; and ``metadata`` carries provider/telemetry data. Frozen; this is
    structure only.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    execution_unit_id: str
    priority: int
    scheduled: bool
    reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionSchedule(BaseModel):
    """Immutable schedule of what could run next (no execution).

    ``frozen=True`` makes instances immutable. ``schedule_id`` is a deterministic
    identifier; ``execution_id`` links to the source execution state;
    ``scheduled_nodes`` are the selected :class:`ScheduledNode` records;
    ``deferred_nodes`` are the ready node ids postponed by ordering;
    ``blocked_nodes`` are the still-blocked node ids; ``execution_order`` is the
    deterministic order of the scheduled node ids; ``scheduling_strategy`` is one
    of the :class:`SchedulingStrategy` labels; and ``metadata`` carries
    provider/telemetry data. The value types are intentionally plain — permissive
    lists of ids — so the :class:`PlanValidator` is the single place the domain
    rules (valid strategy, coherent order, disjoint scheduled/deferred/blocked
    sets) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    schedule_id: str
    execution_id: str
    scheduled_nodes: List[ScheduledNode] = Field(default_factory=list)
    deferred_nodes: List[str] = Field(default_factory=list)
    blocked_nodes: List[str] = Field(default_factory=list)
    execution_order: List[str] = Field(default_factory=list)
    scheduling_strategy: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
