"""Planning provider contract (Sprint 13.1 — reasoning-strategy seam).

Defines the replaceable interface that turns a :class:`PlanningRequest` into a
provider-independent :class:`ExecutionPlan`. Concrete strategies live behind
this interface so the rest of the system stays planner-agnostic: a deterministic
default ships this sprint (:class:`HeuristicPlanningProvider`), and an
LLM-backed strategy can replace it later with no change to services, the engine,
repositories, models, or routers.

A provider only *reasons* — it produces a plan describing what steps *would* be
taken. It performs no tool execution, permission checks, persistence, or runtime
coordination, and never exposes a provider/SDK object across this boundary.
"""

from abc import ABC, abstractmethod

from app.services.planning.models import ExecutionPlan, PlanningRequest


class PlanningProvider(ABC):
    """Replaceable strategy that turns a request into a reasoning plan.

    ``name`` identifies the provider (useful for telemetry/metadata);
    ``create_plan`` builds a provider-independent :class:`ExecutionPlan` from a
    :class:`PlanningRequest`. Implementations own all planning logic behind this
    interface and must never execute a step.
    """

    name: str

    @abstractmethod
    def create_plan(self, request: PlanningRequest) -> ExecutionPlan:
        """Return an :class:`ExecutionPlan` for ``request``.

        Describes what steps *would* be executed; performs no tool execution,
        permission checks, or runtime coordination. No provider/SDK object
        crosses this boundary.
        """
