"""Planner provider contract (Sprint 11.4 — abstraction only).

Defines the replaceable interface that future planning strategies will
implement. This sprint ships ONLY the abstraction: no concrete planning logic,
no AI/LLM calls, no tool execution, no permission checks, no HTTP client, and no
SDK. Concrete providers — added in later sprints — own all planning logic behind
this interface, isolated from services, repositories, models, and routers.
"""

from abc import ABC, abstractmethod

from app.services.planner.models import ExecutionPlan


class PlannerProvider(ABC):
    """Replaceable strategy that turns a user request into an execution plan.

    Concrete implementations (added in a later sprint) live behind this
    interface so the rest of the system stays planner-agnostic. ``name``
    identifies the provider; ``create_plan`` builds a provider-independent
    :class:`ExecutionPlan`. This sprint provides only the abstract contract —
    there is no concrete provider yet, and no step is ever executed.
    """

    name: str

    @abstractmethod
    def create_plan(self, user_request: str) -> ExecutionPlan:
        """Return an :class:`ExecutionPlan` for ``user_request``.

        Describes what steps *would* be executed; performs no tool execution,
        permission checks, or runtime coordination. No provider/SDK object
        crosses this boundary.
        """
