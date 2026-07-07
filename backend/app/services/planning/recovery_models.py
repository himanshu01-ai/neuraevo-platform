"""Recovery models (Sprint 13.13 — immutable recovery-plan DTOs).

Provider-independent, immutable *plan for recovering* a troubled execution: a
chosen recovery strategy, the affected nodes split into recoverable and
unrecoverable sets, whether a human must step in, and a plain-language reason.
This PLANS recovery only; it never retries, resumes, executes, resolves, or
acquires anything — no execution layer exists.

Carries only plain data (ids, a label, bools, plain string lists) — no SDK,
Runtime, Tool, or Planner-framework type crosses this boundary. Strictly additive
to Sprints 13.1–13.12, whose modules are left untouched.
"""

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class RecoveryStrategy(str, Enum):
    """The allowed, deterministic recovery strategies.

    ``NO_ACTION`` means nothing needs recovering; ``RETRY`` re-attempts failed but
    recoverable work; ``RESUME`` continues from a remaining executable path;
    ``REPLAN`` requires rebuilding the plan (deadlock or cycle); and ``ABORT``
    gives up when no recoverable path remains. Kept as a ``str`` enum so each
    serialises to its label.
    """

    NO_ACTION = "NO_ACTION"
    RETRY = "RETRY"
    RESUME = "RESUME"
    REPLAN = "REPLAN"
    ABORT = "ABORT"


class RecoveryPlan(BaseModel):
    """Immutable plan for recovering an execution (no execution).

    ``frozen=True`` makes instances immutable. ``recovery_id`` is a deterministic
    identifier; ``execution_id`` links to the troubled execution;
    ``recovery_strategy`` is one of the :class:`RecoveryStrategy` labels;
    ``affected_nodes`` are the node ids impacted by the problem;
    ``recoverable_nodes`` and ``unrecoverable_nodes`` partition the affected nodes
    by whether a forward path exists; ``requires_user_intervention`` marks that a
    human must step in (only for ``REPLAN``/``ABORT``); ``recovery_reason`` is a
    plain-language justification; and ``metadata`` carries provider/telemetry
    data. The value types are intentionally plain — permissive lists of ids and a
    bool — so the :class:`PlanValidator` is the single place the domain rules
    (valid strategy, recoverable/unrecoverable subsets of affected and disjoint,
    intervention consistent with the strategy) are enforced. Producing this DTO
    executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    recovery_id: str
    execution_id: str
    recovery_strategy: str
    affected_nodes: List[str] = Field(default_factory=list)
    recoverable_nodes: List[str] = Field(default_factory=list)
    unrecoverable_nodes: List[str] = Field(default_factory=list)
    requires_user_intervention: bool
    recovery_reason: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
