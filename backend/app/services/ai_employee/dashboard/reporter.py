"""Dashboard reporter (Sprint 16.14 — assemble composite dashboard reports).

Defines :class:`DashboardReporter`, which assembles the already-projected inspector view
DTOs and the overview into immutable :class:`DashboardReport` s — an overview dashboard,
an engineering dashboard, a system report, and a daily dashboard.

It is a pure formatter: it composes the sections it is given into a report DTO and
executes nothing beyond deterministic assembly. There is no web UI, chart, graph, or
visualisation library — it observes only. Strictly additive to Sprints 1.x–16.13, whose
modules are left untouched.
"""

from typing import Any, Dict

from app.services.ai_employee.dashboard.models import (
    DashboardOverview,
    DashboardReport,
    ReportKind,
)

# The per-inspector section keys a report can carry, in report field order.
_SECTION_KEYS = (
    "workflow",
    "agent",
    "memory",
    "scheduler",
    "recovery",
    "capability",
    "validation",
    "experience",
    "operations",
)


class DashboardReporter:
    """Assembles composite dashboard reports from projected sections (pure assembly).

    Stateless. ``overview_dashboard`` renders the compact health/readiness report;
    ``engineering_dashboard`` and ``daily_dashboard`` render the full report;
    ``system_report`` renders the system-focused report. Each takes the already-projected
    :class:`DashboardOverview` and a mapping of section DTOs and bundles them — it reads
    the inputs only and runs nothing.
    """

    def report(
        self,
        kind: ReportKind,
        overview: DashboardOverview,
        sections: Dict[str, Any],
        sequence: int = 0,
    ) -> DashboardReport:
        """Assemble a :class:`DashboardReport` of ``kind`` bundling ``sections``."""
        fields = {
            key: sections.get(key) for key in _SECTION_KEYS
        }
        return DashboardReport(
            report_id=f"dashboard-{kind.value.lower()}",
            kind=kind,
            overview=overview,
            highlights=self._highlights(overview, sections),
            generated_sequence=sequence,
            report_metadata={"section_count": len(sections)},
            **fields,
        )

    # --- named reports ---------------------------------------------------
    def overview_dashboard(
        self,
        overview: DashboardOverview,
        sections: Dict[str, Any],
        sequence: int = 0,
    ) -> DashboardReport:
        """Assemble the compact overview :class:`DashboardReport`."""
        return self.report(ReportKind.OVERVIEW, overview, sections, sequence)

    def engineering_dashboard(
        self,
        overview: DashboardOverview,
        sections: Dict[str, Any],
        sequence: int = 0,
    ) -> DashboardReport:
        """Assemble the full engineering :class:`DashboardReport`."""
        return self.report(
            ReportKind.ENGINEERING, overview, sections, sequence
        )

    def system_report(
        self,
        overview: DashboardOverview,
        sections: Dict[str, Any],
        sequence: int = 0,
    ) -> DashboardReport:
        """Assemble the system-focused :class:`DashboardReport`."""
        return self.report(ReportKind.SYSTEM, overview, sections, sequence)

    def daily_dashboard(
        self,
        overview: DashboardOverview,
        sections: Dict[str, Any],
        sequence: int = 0,
    ) -> DashboardReport:
        """Assemble the daily :class:`DashboardReport`."""
        return self.report(ReportKind.DAILY, overview, sections, sequence)

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _highlights(
        overview: DashboardOverview, sections: Dict[str, Any]
    ) -> list:
        """Return deterministic plain-text headline lines for a report."""
        return [
            f"production {'ready' if overview.ready else 'not ready'} "
            f"({overview.state})",
            f"experience grade {overview.grade}",
            f"{overview.healthy_subsystems}/{overview.total_subsystems} "
            f"subsystems healthy",
            f"{overview.total_tasks} workflow(s); "
            f"{overview.active_sessions} active session(s)",
            f"{overview.open_issues} blocking issue(s)",
            f"{len(sections)} section(s) reported",
        ]
