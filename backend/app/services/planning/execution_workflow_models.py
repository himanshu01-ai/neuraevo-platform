"""Execution workflow models (Sprint 13.6 — immutable workflow DTO).

Provider-independent, immutable structure describing *how a plan's steps would be
coordinated* for eventual execution: an ordered, grouped step list, an execution
mode, a status, and whether the workflow can be resumed. This is COORDINATION
PLANNING ONLY: it describes a workflow; it never executes, resolves, or acquires
anything — no execution layer exists.

Carries only plain data (ids, labels, ints, bools, nested plain step records) —
no SDK, Runtime, Tool, or Planner-framework type crosses this boundary. Strictly
additive to Sprints 13.1–13.5, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStatus(str, Enum):
    """The allowed, deterministic workflow statuses.

    ``PLANNED`` — structured but not activated. ``READY`` — may proceed now.
    ``WAITING`` — waiting on the user. ``BLOCKED`` — held until requirements are
    met. These are the only permitted values; a status is always chosen
    deterministically. Kept as a ``str`` enum so it serialises to its label.
    """

    PLANNED = "PLANNED"
    READY = "READY"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"


class ExecutionMode(str, Enum):
    """The allowed, deterministic workflow execution modes.

    ``SEQUENTIAL`` runs steps one after another; ``PARALLEL`` groups steps to run
    at once; ``HYBRID`` mixes both. These are the only permitted values. Kept as
    a ``str`` enum so it serialises to its label.
    """

    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    HYBRID = "HYBRID"


class WorkflowStep(BaseModel):
    """A single, immutable step within an :class:`ExecutionWorkflow`.

    ``step_number`` preserves the plan's ordering; ``description`` restates what
    the step does; ``group`` is the 1-based execution group (steps sharing a
    group may run together); ``depends_on`` preserves the plan's dependencies.
    Frozen — a workflow step cannot be mutated. This is structure only; nothing
    is executed.
    """

    model_config = ConfigDict(frozen=True)

    step_number: int
    description: str
    group: int
    depends_on: List[int] = Field(default_factory=list)


class ExecutionWorkflow(BaseModel):
    """Immutable coordination structure for a plan's steps (no execution).

    ``frozen=True`` makes instances immutable. ``workflow_id`` is a deterministic
    identifier; ``workflow_status`` is one of the :class:`WorkflowStatus` labels;
    ``ordered_steps`` are the grouped, order-preserving :class:`WorkflowStep`
    records; ``estimated_total_steps`` counts them; ``execution_mode`` is one of
    the :class:`ExecutionMode` labels; ``resumable`` marks whether the workflow
    can be paused and continued; and ``metadata`` carries provider/telemetry
    data. The value types are intentionally plain — permissive :class:`str`/
    :class:`int` — so the :class:`PlanValidator` is the single place the domain
    rules (valid status/mode, non-negative and consistent counts, unique steps,
    positive groups) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    workflow_status: str
    ordered_steps: List[WorkflowStep] = Field(default_factory=list)
    estimated_total_steps: int
    execution_mode: str
    resumable: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)
