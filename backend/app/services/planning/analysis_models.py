"""Plan analysis model (Sprint 13.2 — immutable analysis DTO).

A provider-independent, immutable summary of what an :class:`ExecutionPlan`
needs before it could run: whether it is ready, whether it needs confirmation or
clarification, what information is missing, which questions to ask, a
deterministic risk note, and a confidence score. It carries only plain data — no
provider/SDK object crosses this boundary — and describes a plan; it executes
nothing.

This is strictly additive to Sprint 13.1: that module's DTOs (``ExecutionStep`` /
``ExecutionPlan`` / ``PlanningRequest``) are left untouched, and this analysis
shape lives in its own file alongside them.
"""

from typing import Annotated, List

from pydantic import BaseModel, ConfigDict, Field

# Confidence is a probability-like score constrained to the unit interval.
_Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class PlanAnalysis(BaseModel):
    """Immutable analysis of an :class:`ExecutionPlan` (reasoning only).

    ``frozen=True`` makes instances immutable, so a completed analysis cannot be
    mutated. ``ready_for_execution`` is True only when nothing is missing;
    ``requires_confirmation`` mirrors the plan's confirmation intent;
    ``requires_clarification`` is True when there are questions to ask before
    proceeding; ``missing_information`` and ``clarification_questions`` list what
    the agent still needs and what it would ask; ``risk_summary`` is a
    deterministic plain-language note; and ``confidence`` is a ``0.0``–``1.0``
    score (enforced by the DTO). Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    ready_for_execution: bool
    requires_confirmation: bool
    requires_clarification: bool
    missing_information: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)
    risk_summary: str
    confidence: _Confidence
