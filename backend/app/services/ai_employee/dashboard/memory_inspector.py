"""Memory inspector (Sprint 16.14 — visualise the memory subsystem status).

Defines :class:`MemoryInspector`, which projects the memory view of the dashboard — a
memory summary, memory categories, and memory statistics — by *reading* the memory
subsystem status the frozen Sprint 16.11 :class:`EnterpriseOperationsManager` reports
through its health/observability surface. It never executes a workflow, changes
behaviour, or modifies state.

The operational surfaces the dashboard is allowed to use expose the memory subsystem's
health, not its individual records, so the memory summary/statistics are its status
projection and categories are reported when present. It observes only: it reads and
executes, delegates, and stores nothing. Strictly additive to Sprints 1.x–16.13, whose
modules are left untouched.
"""

from app.services.ai_employee.dashboard import common
from app.services.ai_employee.dashboard.models import MemoryDashboard


class MemoryInspector:
    """Projects the memory dashboard from the memory subsystem status (read-only).

    Constructed with an injected :class:`EnterpriseOperationsManager` (constructor
    injection; it instantiates none). ``dashboard`` reads the memory component's status
    and reports its summary, categories, and statistics. It is stateless and reads only —
    it runs nothing.
    """

    def __init__(self, operations) -> None:
        self.operations = operations

    def dashboard(self) -> MemoryDashboard:
        """Return the :class:`MemoryDashboard` for the memory subsystem."""
        component = common.component_map(self.operations).get("memory")
        present = component is not None
        healthy = bool(component.healthy) if present else False
        state = component.state.value if present else "UNKNOWN"
        return MemoryDashboard(
            present=present,
            healthy=healthy,
            state=state,
            categories={},
            statistics={
                "reported": int(present),
                "healthy": int(healthy),
            },
            dashboard_metadata={"source": "operations.health"},
        )
