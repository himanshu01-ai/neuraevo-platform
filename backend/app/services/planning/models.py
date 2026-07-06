"""Planning Engine models (Sprint 13.1 — provider-independent DTOs).

Strongly-typed, provider-independent shapes describing a *reasoned* (not
executed) plan the AI Employee would follow to satisfy a user request. They
carry only plain data (goal, summary, ordered reasoning steps, open questions,
metadata) so no provider/SDK object is ever exposed across the planning
boundary. No execution, tool calls, permission checks, AI/LLM, or provider
logic lives here.

These are deliberately distinct from the Sprint 11.4 ``app.services.planner``
DTOs (``ExecutionPlan`` / ``PlanningStep``), which describe a low-level sequence
of *tool* invocations (tool name + arguments). The Planning Engine reasons at a
higher, cognitive level: each :class:`ExecutionStep` is a thinking step with a
rationale, an *optional* expected tool, and explicit dependencies; an
:class:`ExecutionPlan` adds a goal, summary, open questions, confirmation
intent, and metadata. The frozen Sprint 11.4 module is left untouched.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]

# A 1-based step identifier / dependency reference (0 or negative is invalid).
_PositiveInt = Annotated[int, Field(ge=1)]


class PlanStepStatus(str, Enum):
    """Lifecycle status of an :class:`ExecutionStep`.

    The Planning Engine only *plans*; it never executes. Every step a plan
    produces is therefore ``PLANNED``. Execution states (running, completed,
    failed, …) intentionally do not exist here — they belong to the future
    execution layer, not to this reasoning-only sprint. Kept as a ``str`` enum
    so it serialises to a stable ``"planned"`` value.
    """

    PLANNED = "planned"


class ExecutionStep(BaseModel):
    """A single, immutable reasoning step within an :class:`ExecutionPlan`.

    ``frozen=True`` makes instances immutable, so a step cannot be mutated after
    the planner produces it. ``step_number`` is its 1-based position;
    ``description`` states what the step does; ``reason`` explains *why* it is
    needed; ``expected_tool`` optionally names the tool the step would later use
    (a hint only — nothing is bound or executed); ``dependencies`` list the
    earlier ``step_number`` values this step relies on; ``status`` is always
    ``PLANNED`` in this reasoning-only sprint. This is a plan only — nothing is
    executed and no permission is checked.
    """

    model_config = ConfigDict(frozen=True)

    step_number: _PositiveInt
    description: _NonEmptyStr
    reason: _NonEmptyStr
    expected_tool: Optional[_NonEmptyStr] = None
    dependencies: List[_PositiveInt] = Field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PLANNED


class ExecutionPlan(BaseModel):
    """An immutable, ordered plan the AI Employee *would* follow (no execution).

    ``frozen=True`` makes instances immutable, so a plan cannot be mutated after
    a provider returns it. ``goal`` is the outcome the plan targets; ``summary``
    is a short human overview; ``steps`` are the ordered reasoning steps;
    ``missing_information`` lists what the agent still needs from the user before
    it could proceed; ``requires_user_confirmation`` signals that a future
    execution layer must obtain approval first; ``estimated_step_count`` defaults
    to ``len(steps)`` when omitted; ``metadata`` carries provider/telemetry data
    that is not itself a step. Building this DTO performs no execution.
    """

    model_config = ConfigDict(frozen=True)

    goal: _NonEmptyStr
    summary: _NonEmptyStr
    steps: List[ExecutionStep] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    estimated_step_count: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _default_estimated_step_count(cls, data: Any) -> Any:
        """Default ``estimated_step_count`` to the number of steps when omitted.

        Keeps the count consistent for the common case (the planner does not set
        it explicitly) while still honouring an explicit value when a caller
        supplies one — e.g. a partial plan that expects more steps than it has
        enumerated so far.
        """
        if isinstance(data, dict) and data.get("estimated_step_count") is None:
            steps = data.get("steps") or []
            try:
                data = {**data, "estimated_step_count": len(steps)}
            except TypeError:
                # ``steps`` is not sized (invalid input) — let field validation
                # surface the real error rather than masking it here.
                pass
        return data


class PlanningRequest(BaseModel):
    """Provider-independent input to the :class:`PlanningEngine`.

    ``user_request`` is the required, non-empty ask being planned.
    ``conversation_context`` and ``memory_summary`` are optional plain-text
    summaries the caller (e.g. a future Conversation Runtime integration) distils
    from the live conversation and the Memory Engine; they default to empty so
    the engine stays decoupled from those foundation types and remains
    provider-independent. This is an input only — constructing it plans nothing.
    """

    user_request: _NonEmptyStr
    conversation_context: str = ""
    memory_summary: str = ""
