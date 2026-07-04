"""Planner framework models (Sprint 11.4 — provider-independent DTOs).

Strongly-typed, provider-independent shapes describing a planned (not executed)
sequence of tool steps. They carry only plain data (tool name, argument dict,
description) so no provider/SDK object is ever exposed across the planner
boundary. No execution, tool calls, permission checks, or provider logic live
here.
"""

from typing import Annotated, Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


class PlanningStep(BaseModel):
    """A single planned tool step (immutable, provider-independent).

    ``tool_name`` names the tool the step would invoke; ``arguments`` are the
    intended inputs (defaulting to empty); ``description`` explains the step in
    plain language. This is a plan only — nothing is executed.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: _NonEmptyStr
    arguments: Dict[str, Any] = Field(default_factory=dict)
    description: _NonEmptyStr


class ExecutionPlan(BaseModel):
    """An immutable, ordered plan of steps that *would* be executed.

    ``frozen=True`` makes instances immutable, so a plan cannot be mutated after
    a provider returns it. ``steps`` defaults to an empty list (an empty plan).
    Building this DTO performs no execution.
    """

    model_config = ConfigDict(frozen=True)

    steps: List[PlanningStep] = Field(default_factory=list)
