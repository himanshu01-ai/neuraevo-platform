"""Documentation generator (Sprint 16.15 — generate release documentation).

Defines :class:`DocumentationGenerator`, which generates the release documentation — an
architecture summary, a module inventory, a service inventory, a capability inventory,
and release notes — by *reading* the frozen Sprint 16.14
:class:`DeveloperDashboardManager` for the live overview and observed capabilities. It
never executes a workflow, changes behaviour, or modifies state.

The inventories are the platform's canonical, stable lists (augmented with observed
capability usage from the dashboard); the release notes are deterministic lines derived
from the overview. It observes only: it reads and executes, delegates, and stores
nothing. Strictly additive to Sprints 1.x–16.14, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.release.models import (
    RELEASE_VERSION,
    DocumentationReport,
)

# The canonical AI Employee sub-modules that make up the backend.
_MODULE_INVENTORY = (
    "ai_employee",
    "approval",
    "notification",
    "persistence",
    "memory",
    "scheduler",
    "recovery",
    "coordination",
    "service",
    "operations",
    "experience",
    "validation",
    "dashboard",
    "release",
)

# The canonical stable public services/managers the backend exposes.
_SERVICE_INVENTORY = (
    "AIEmployeeService",
    "EnterpriseOperationsManager",
    "ExperienceIntelligenceManager",
    "ProductionValidationManager",
    "DeveloperDashboardManager",
    "ReleaseManager",
)

# The canonical capabilities the runtime supports (names only — no capability import).
_CAPABILITY_INVENTORY = (
    "browser",
    "python",
    "filesystem",
    "email",
    "calendar",
    "github",
)

_ARCHITECTURE_SUMMARY = (
    "Layered AI Employee backend: the AIEmployee foundation orchestrates Planning "
    "and the Workflow Coordinator; the Service Layer exposes stable task control; "
    "the Enterprise Operations, Experience Intelligence, Production Validation, and "
    "Developer Dashboard layers wrap it with operations, analytics, validation, and "
    "visualisation. Constructor DI only; frozen DTOs; provider-independent."
)


class DocumentationGenerator:
    """Generates release documentation from the platform inventories (read-only).

    Constructed with an injected :class:`DeveloperDashboardManager` (constructor
    injection; it instantiates none). ``generate`` assembles the architecture summary,
    module/service/capability inventories, and release notes into a
    :class:`DocumentationReport`. It reads the dashboard overview only — it runs nothing.
    """

    def __init__(self, dashboard) -> None:
        self.dashboard = dashboard

    def architecture_summary(self) -> str:
        """Return the deterministic architecture summary."""
        return _ARCHITECTURE_SUMMARY

    def module_inventory(self) -> List[str]:
        """Return the canonical module inventory."""
        return list(_MODULE_INVENTORY)

    def service_inventory(self) -> List[str]:
        """Return the canonical service inventory."""
        return list(_SERVICE_INVENTORY)

    def capability_inventory(self) -> List[str]:
        """Return the capability inventory (canonical names plus observed usage)."""
        observed = set(
            self.dashboard.capability.dashboard().capability_usage
        )
        return sorted(set(_CAPABILITY_INVENTORY) | observed)

    def release_notes(self) -> List[str]:
        """Return the deterministic release notes for this candidate."""
        overview = self.dashboard.overview()
        return [
            f"Release {RELEASE_VERSION}: AI Employee backend release candidate.",
            "Backend contracts frozen; DTOs immutable; provider-independent.",
            f"Production readiness: "
            f"{'ready' if overview.ready else 'not ready'} ({overview.state}).",
            f"{overview.healthy_subsystems}/{overview.total_subsystems} "
            f"subsystems healthy.",
            f"Experience grade: {overview.grade}.",
            f"{len(_MODULE_INVENTORY)} modules; "
            f"{len(_SERVICE_INVENTORY)} services; "
            f"{len(_CAPABILITY_INVENTORY)} capabilities.",
        ]

    def generate(self) -> DocumentationReport:
        """Return the assembled :class:`DocumentationReport`."""
        return DocumentationReport(
            architecture_summary=self.architecture_summary(),
            module_inventory=self.module_inventory(),
            service_inventory=self.service_inventory(),
            capability_inventory=self.capability_inventory(),
            release_notes=self.release_notes(),
            doc_metadata={"version": RELEASE_VERSION},
        )
