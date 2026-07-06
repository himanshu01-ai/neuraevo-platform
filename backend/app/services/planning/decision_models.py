"""Decision models (Sprint 13.4 — immutable execution-decision DTO).

Provider-independent, immutable verdict on whether a plan may proceed, produced
by weighing an :class:`ExecutionPlan`, its :class:`PlanAnalysis`, and its
:class:`ExecutionPreparation`. This is a DECISION ONLY: it classifies readiness;
it never executes, resolves, or acquires anything.

Carries only plain data (a status label, a bool, plain strings, a float) — no
SDK, Runtime, Tool, or Planner-framework type crosses this boundary. Strictly
additive to Sprints 13.1–13.3, whose modules are left untouched.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class DecisionStatus(str, Enum):
    """The allowed, deterministic execution decisions.

    ``APPROVED`` — every prerequisite is satisfied and the plan may proceed.
    ``WAITING_FOR_INFORMATION`` — required information is still missing.
    ``WAITING_FOR_CONFIRMATION`` — ready, but user confirmation is required.
    ``BLOCKED`` — unmet capability/permission/account requirements stand in the
    way. ``REJECTED`` — the plan cannot be executed as formulated. These are the
    only permitted values; a status is always chosen deterministically. Kept as a
    ``str`` enum so it serialises to its plain label.
    """

    APPROVED = "APPROVED"
    WAITING_FOR_INFORMATION = "WAITING_FOR_INFORMATION"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class ExecutionDecision(BaseModel):
    """Immutable decision about an :class:`ExecutionPlan` (no execution).

    ``frozen=True`` makes instances immutable. ``status`` is one of the
    :class:`DecisionStatus` labels; ``can_execute`` is True only when the status
    is ``APPROVED``; ``reason`` is a deterministic plain-language justification;
    ``blocking_reasons`` lists what still stands in the way (empty when
    approved); and ``confidence`` is the ``0.0``–``1.0`` score carried from the
    analysis. The value types are intentionally plain — a permissive
    :class:`str`/:class:`float` — so the :class:`PlanValidator` is the single
    place the domain rules (valid status, confidence range, consistency, no
    duplicates) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    status: str
    can_execute: bool
    reason: str
    blocking_reasons: List[str] = Field(default_factory=list)
    confidence: float
