"""Agent inspector (Sprint 16.14 — visualise agent engagements from the service).

Defines :class:`AgentInspector`, which projects the agent view of the dashboard —
registered agents, agent status, active work, and a coordination summary — by *reading*
the frozen Sprint 16.10 :class:`AIEmployeeService`'s sessions and tasks. It never
executes a workflow, changes behaviour, or modifies state.

Each employee that owns a session is one observed agent; its active sessions are its
active work. The inspector projects these into a deterministic :class:`AgentDashboard`.
It observes only: it reads and executes, delegates, and stores nothing. Strictly
additive to Sprints 1.x–16.13, whose modules are left untouched.
"""

from app.services.ai_employee.dashboard.models import AgentDashboard


class AgentInspector:
    """Projects the agent dashboard from the service sessions (read-only).

    Constructed with an injected :class:`AIEmployeeService` (constructor injection; it
    instantiates none). ``dashboard`` reads the sessions and tasks and reports the
    registered agents, active work, and coordination counters. It is stateless and reads
    only — it runs nothing.
    """

    def __init__(self, service) -> None:
        self.service = service

    def dashboard(self) -> AgentDashboard:
        """Return the :class:`AgentDashboard` for the observed agents."""
        sessions = self.service.session_manager
        all_sessions = sessions.list()
        active_sessions = sessions.active()
        registered = sorted(
            {session.employee_id for session in all_sessions if session.employee_id}
        )
        task_count = len(self.service.list_tasks())
        return AgentDashboard(
            registered_agents=registered,
            agent_count=len(registered),
            active_work=len(active_sessions),
            session_counts={
                "total": len(all_sessions),
                "active": len(active_sessions),
            },
            coordination={
                "agents": len(registered),
                "sessions": len(all_sessions),
                "tasks": task_count,
            },
            dashboard_metadata={"source": "ai_employee_service"},
        )
