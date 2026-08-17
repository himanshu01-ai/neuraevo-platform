"""Health manager (Sprint 16.10 — expose provider-independent platform health).

Defines :class:`HealthManager`, which reports the health and readiness of the AI
Employee platform's subsystems — Planning, Runtime, AIEmployee, Memory, Scheduler,
Recovery, and Persistence — as provider-independent :class:`HealthStatus` DTOs. It
is given a plain availability flag per subsystem (a boolean the composition root
derives from whether each seam is wired) and derives the overall state from them:
all up is ``HEALTHY``, some up is ``DEGRADED``, none up is ``UNHEALTHY``.

It reports only: it holds no provider/SDK object, calls no subsystem, and executes,
delegates, and stores nothing. It never touches the Workflow Coordinator, a
capability, a repository, a database, an LLM provider, a thread, or the network.
Deterministic and stateless. Strictly additive to Sprints 1.x–16.9, whose modules
are left untouched.
"""

from typing import Dict

from app.services.ai_employee.service.models import HealthState, HealthStatus

# The canonical, ordered subsystems the platform reports health for.
HEALTH_COMPONENTS = (
    "planning",
    "runtime",
    "ai_employee",
    "memory",
    "scheduler",
    "recovery",
    "persistence",
)


class HealthManager:
    """Reports platform health/readiness from injected availability flags.

    Constructed with a ``components`` map of subsystem name -> available flag; any
    canonical subsystem missing from the map is treated as unavailable. ``health``
    returns an overall :class:`HealthStatus` (``HEALTHY`` when all are up,
    ``DEGRADED`` when some are, ``UNHEALTHY`` when none are) with a per-component
    breakdown; ``readiness`` reports whether every subsystem is up. Deterministic and
    stateless; it reports only and runs nothing.
    """

    def __init__(self, components: Dict[str, bool]) -> None:
        # Normalise to the canonical component set; missing => unavailable.
        self._components: Dict[str, bool] = {
            name: bool(components.get(name, False))
            for name in HEALTH_COMPONENTS
        }

    def health(self) -> HealthStatus:
        """Return the overall :class:`HealthStatus` with a per-component breakdown."""
        breakdown = {
            name: (
                HealthState.HEALTHY if available else HealthState.UNHEALTHY
            ).value
            for name, available in self._components.items()
        }
        up = sum(1 for available in self._components.values() if available)
        total = len(self._components)
        if up == total:
            state = HealthState.HEALTHY
        elif up == 0:
            state = HealthState.UNHEALTHY
        else:
            state = HealthState.DEGRADED
        return HealthStatus(
            state=state,
            ready=state == HealthState.HEALTHY,
            components=breakdown,
            detail=f"{up}/{total} subsystems healthy",
        )

    def readiness(self) -> HealthStatus:
        """Return a readiness :class:`HealthStatus` (``ready`` iff every subsystem is up).

        Shares the health breakdown but frames the result for readiness: the platform
        is ready only when no subsystem is down.
        """
        report = self.health()
        return report.model_copy(
            update={
                "ready": report.state == HealthState.HEALTHY,
                "detail": (
                    "ready"
                    if report.state == HealthState.HEALTHY
                    else "not ready"
                ),
            }
        )
