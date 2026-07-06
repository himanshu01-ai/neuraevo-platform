"""Planning package (Sprint 13.1 — Intelligent Planning Engine).

Ships the reasoning-only planning layer that teaches the AI Employee to think
before acting:

* the provider-independent DTOs — :class:`ExecutionStep`, :class:`ExecutionPlan`,
  :class:`PlanningRequest`, and the :class:`PlanStepStatus` enum;
* the :class:`PlanningProvider` seam plus the deterministic default
  :class:`HeuristicPlanningProvider`;
* the :class:`PlanValidator` (with :class:`PlanValidationError`) and the
  :class:`PlanningExplanationBuilder`; and
* the :class:`PlanningEngine` coordinator (reason -> validate -> explain).

The engine produces an :class:`ExecutionPlan` and never executes it. This layer
is distinct from — and leaves untouched — the frozen Sprint 11.4
``app.services.planner`` tool-step framework.
"""

from app.services.planning.models import (
    ExecutionPlan,
    ExecutionStep,
    PlanningRequest,
    PlanStepStatus,
)
from app.services.planning.plan_explanation_builder import (
    PlanningExplanationBuilder,
)
from app.services.planning.plan_validator import PlanValidationError, PlanValidator
from app.services.planning.planning_engine import PlanningEngine
from app.services.planning.providers import (
    HeuristicPlanningProvider,
    PlanningProvider,
)

__all__ = [
    "PlanningEngine",
    "PlanningProvider",
    "HeuristicPlanningProvider",
    "PlanValidator",
    "PlanValidationError",
    "PlanningExplanationBuilder",
    "ExecutionPlan",
    "ExecutionStep",
    "PlanningRequest",
    "PlanStepStatus",
]
