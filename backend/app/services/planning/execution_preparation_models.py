"""Execution preparation models (Sprint 13.3 — immutable preparation DTO).

Provider-independent, immutable description of *what an ExecutionPlan would
require to run* — the capabilities, external services, and permissions involved,
how many steps, whether it could start immediately, what blocks it, and which
execution strategy fits. This is PREPARATION ONLY: it names requirements; it
never resolves, acquires, or executes anything.

Carries only plain data (strings, ints, bools) — no SDK, Runtime, Tool, or
Planner-framework type crosses this boundary. Strictly additive to Sprints 13.1
and 13.2, whose modules are left untouched.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStrategy(str, Enum):
    """The allowed, deterministic execution strategies.

    ``SEQUENTIAL`` runs steps one after another; ``PARALLEL`` runs independent
    steps at once; ``HYBRID`` mixes both. These are the only permitted values —
    a strategy is always chosen deterministically, never guessed. Kept as a
    ``str`` enum so it serialises to its plain label.
    """

    SEQUENTIAL = "Sequential"
    PARALLEL = "Parallel"
    HYBRID = "Hybrid"


class ExecutionPreparation(BaseModel):
    """Immutable preparation summary for an :class:`ExecutionPlan` (no execution).

    ``frozen=True`` makes instances immutable. ``required_capabilities`` names the
    high-level abilities the plan would use (e.g. ``Calendar``, ``Browser``);
    ``external_services`` names the third-party services those touch;
    ``permissions_required`` names the permissions that would have to be granted;
    ``estimated_execution_steps`` counts the plan's steps;
    ``can_execute_immediately`` is True only when nothing blocks it;
    ``blocked_by`` lists the reasons it cannot start yet (never empty strings);
    and ``execution_strategy`` is one of the :class:`ExecutionStrategy` labels.
    The value types are intentionally plain — a permissive :class:`int`/:class:`str`
    — so the :class:`PlanValidator` is the single place the domain rules
    (non-negative steps, valid strategy, no duplicates) are enforced. Producing
    this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    required_capabilities: List[str] = Field(default_factory=list)
    external_services: List[str] = Field(default_factory=list)
    permissions_required: List[str] = Field(default_factory=list)
    estimated_execution_steps: int
    can_execute_immediately: bool
    blocked_by: List[str] = Field(default_factory=list)
    execution_strategy: str
