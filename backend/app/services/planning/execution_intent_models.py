"""Execution intent models (Sprint 13.5 — immutable execution-intent DTO).

Provider-independent, immutable statement of *what the system intends to do* with
a plan, derived from its :class:`ExecutionDecision`. This is INTENT ONLY: it
records an intention (execute now, wait, defer, or cancel); it never executes,
resolves, or acquires anything — no execution layer exists.

Carries only plain data (a label, bools, plain strings, an int) — no SDK,
Runtime, Tool, or Planner-framework type crosses this boundary. Strictly additive
to Sprints 13.1–13.4, whose modules are left untouched.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class ExecutionIntentType(str, Enum):
    """The allowed, deterministic execution intents.

    ``EXECUTE_NOW`` — the plan may be carried out immediately.
    ``WAIT_FOR_USER`` — the system is waiting on the user (information or
    confirmation). ``DEFER`` — set aside until blocking requirements are
    resolved. ``CANCEL`` — abandon the plan. These are the only permitted
    values; an intent is always chosen deterministically. Kept as a ``str`` enum
    so it serialises to its plain label.
    """

    EXECUTE_NOW = "EXECUTE_NOW"
    WAIT_FOR_USER = "WAIT_FOR_USER"
    DEFER = "DEFER"
    CANCEL = "CANCEL"


class ExecutionIntent(BaseModel):
    """Immutable execution intent for a plan (no execution).

    ``frozen=True`` makes instances immutable. ``intent`` is one of the
    :class:`ExecutionIntentType` labels; ``should_execute`` is True only when the
    intent is ``EXECUTE_NOW``; ``requires_user_action`` is True only when the
    intent is ``WAIT_FOR_USER``; ``recommended_next_step`` is a deterministic
    plain-language pointer to what should happen next; ``execution_priority`` is a
    non-negative urgency score; and ``defer_reason`` explains a deferral (empty
    unless the intent is ``DEFER``). The value types are intentionally plain — a
    permissive :class:`str`/:class:`int` — so the :class:`PlanValidator` is the
    single place the domain rules (valid intent, non-negative priority,
    consistency) are enforced. Producing this DTO executes nothing.
    """

    model_config = ConfigDict(frozen=True)

    intent: str
    should_execute: bool
    requires_user_action: bool
    recommended_next_step: str
    execution_priority: int
    defer_reason: str = ""
