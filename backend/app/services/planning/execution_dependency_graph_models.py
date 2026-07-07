"""Execution dependency graph models (Sprint 13.10 — immutable graph DTOs).

Provider-independent, immutable model of *how a queue's tasks depend on one
another*: a set of nodes (one per execution unit), the directed edges between
them, and derived structure (root/leaf/ready/blocked nodes and whether the graph
contains cycles). This models task RELATIONSHIPS ONLY: it never executes,
resolves, or acquires anything — no execution layer exists.

Carries only plain data (ids, plain string lists, bools, nested plain node/edge
records) — no SDK, Runtime, Tool, or Planner-framework type crosses this
boundary. Strictly additive to Sprints 13.1–13.9, whose modules are left
untouched.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class ExecutionEdge(BaseModel):
    """A single, immutable directed dependency edge (no execution).

    An edge ``source_node -> target_node`` means ``target_node`` depends on
    ``source_node`` — the source is a prerequisite that would run first. Frozen;
    this is structure only.
    """

    model_config = ConfigDict(frozen=True)

    source_node: str
    target_node: str


class ExecutionNode(BaseModel):
    """A single, immutable node in the dependency graph (no execution).

    ``node_id`` is the graph identifier; ``execution_unit_id`` links to the queue
    unit; ``dependencies`` are the node ids this node depends on; ``dependents``
    are the node ids that depend on this node; ``ready`` marks a node that may
    start; ``blocked`` is its inverse; and ``metadata`` carries provider/telemetry
    data. Frozen; this is structure only.
    """

    model_config = ConfigDict(frozen=True)

    node_id: str
    execution_unit_id: str
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    ready: bool
    blocked: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionDependencyGraph(BaseModel):
    """Immutable dependency graph over a queue's tasks (no execution).

    ``frozen=True`` makes instances immutable. ``graph_id`` is a deterministic
    identifier; ``nodes`` and ``edges`` are the graph structure; ``root_nodes``
    have no dependencies; ``leaf_nodes`` have no dependents; ``ready_nodes`` and
    ``blocked_nodes`` partition the nodes by readiness; ``has_cycles`` marks a
    non-acyclic graph; and ``metadata`` carries provider/telemetry data. The
    value types are intentionally plain — permissive lists of ids — so the
    :class:`PlanValidator` is the single place the domain rules (unique nodes,
    edges/dependencies referencing known nodes, coherent root/leaf/ready/blocked
    sets) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    graph_id: str
    nodes: List[ExecutionNode] = Field(default_factory=list)
    edges: List[ExecutionEdge] = Field(default_factory=list)
    root_nodes: List[str] = Field(default_factory=list)
    leaf_nodes: List[str] = Field(default_factory=list)
    ready_nodes: List[str] = Field(default_factory=list)
    blocked_nodes: List[str] = Field(default_factory=list)
    has_cycles: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)
