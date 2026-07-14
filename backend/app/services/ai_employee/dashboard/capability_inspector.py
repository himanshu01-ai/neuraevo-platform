"""Capability inspector (Sprint 16.14 — visualise capability usage and success).

Defines :class:`CapabilityInspector`, which projects the capability view of the
dashboard — capability usage, execution statistics, and success rates — by *reading*
the frozen Sprint 16.12 :class:`ExperienceIntelligenceManager`'s already-computed
behaviour and experience metrics. It never executes a capability, changes behaviour, or
modifies state.

Capability usage comes from the behaviour metrics and per-capability success from the
experience metrics — both are deterministic reads the experience platform already
computes. It observes only: it reads and executes, delegates, and stores nothing.
Strictly additive to Sprints 1.x–16.13, whose modules are left untouched.
"""

from app.services.ai_employee.dashboard.models import CapabilityDashboard


class CapabilityInspector:
    """Projects the capability dashboard from the experience metrics (read-only).

    Constructed with an injected :class:`ExperienceIntelligenceManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the behaviour and experience
    metrics and reports capability usage, success rates, and aggregate execution
    statistics. It is stateless and reads only — it runs nothing.
    """

    def __init__(self, experience) -> None:
        self.experience = experience

    def dashboard(self) -> CapabilityDashboard:
        """Return the :class:`CapabilityDashboard` for the observed capabilities."""
        behavior = self.experience.behavior()
        metrics = self.experience.experience()
        return CapabilityDashboard(
            capability_usage=dict(behavior.capability_usage),
            success_rates=dict(metrics.capability_success),
            execution={
                "task_count": metrics.task_count,
                "task_success_rate": metrics.task_success_rate,
                "average_execution_units": metrics.average_execution_units,
            },
            dashboard_metadata={"source": "experience_intelligence"},
        )
