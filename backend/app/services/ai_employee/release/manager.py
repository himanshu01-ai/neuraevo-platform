"""Release manager (Sprint 16.15 — coordinate release-candidate preparation).

Defines :class:`ReleaseManager`, the coordinator of the Release Candidate backend. It
coordinates release preparation over its injected components — the
:class:`ContractManager`, :class:`DependencyAuditor`, :class:`ConfigurationAuditor`,
:class:`DocumentationGenerator`, :class:`BackupValidator`, and :class:`ReleaseReporter`
— and *delegates to the frozen Sprint 16.14* :class:`DeveloperDashboardManager` for the
platform's overall state:

    release_readiness    (the overall readiness verdict)
    freeze_contracts     (freeze the stable public contracts)
    audit                (the dependency + configuration + backup audit verdict)
    generate_release     (the comprehensive release report)
    summary              (the compact release-candidate go/no-go)

This sprint adds release infrastructure only. It never executes a workflow or a
capability, never calls the Workflow Coordinator, and never modifies platform state —
the platform's overall state is read only through the
:class:`DeveloperDashboardManager`. Constructor injection only; it holds no mutable
state of its own — no static, singleton, or service-locator state. Strictly additive to
Sprints 1.x–16.14, whose modules are left untouched.
"""

from typing import Tuple

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    BackupReport,
    ConfigurationAudit,
    DependencyReport,
    DocumentationReport,
    ReleaseCandidateSummary,
    ReleaseReport,
    ReleaseStatus,
)


class ReleaseManager:
    """Coordinates release-candidate preparation over its components and the dashboard.

    Constructed with an injected :class:`ContractManager`, :class:`DependencyAuditor`,
    :class:`ConfigurationAuditor`, :class:`DocumentationGenerator`,
    :class:`BackupValidator`, :class:`ReleaseReporter`, and the frozen Sprint 16.14
    :class:`DeveloperDashboardManager` (constructor injection; it instantiates none). It
    freezes contracts, audits dependencies/configuration/backup, generates
    documentation, and derives the release go/no-go, reading the platform's overall state
    only through the dashboard — it prepares only and executes no workflow. It holds no
    mutable state of its own.
    """

    def __init__(
        self,
        contract,
        dependency,
        configuration,
        documentation,
        backup,
        reporter,
        dashboard,
    ) -> None:
        self.contract = contract
        self.dependency = dependency
        self.configuration = configuration
        self.documentation = documentation
        self.backup = backup
        self.reporter = reporter
        self.dashboard = dashboard

    # --- coordination ----------------------------------------------------
    def freeze_contracts(self) -> ReleaseStatus:
        """Freeze the stable public contracts and return the freeze verdict."""
        return self.contract.freeze_summary()

    def audit(self) -> ReleaseStatus:
        """Return the dependency + configuration + backup audit verdict."""
        dependencies = self.dependency.validate()
        configuration = self.configuration.validate()
        backup = self.backup.validate()
        issues = [
            *dependencies.issues,
            *configuration.issues,
            *backup.issues,
        ]
        return common.status(
            "release_audit",
            issues,
            detail=(
                "audits passed"
                if not common.blockers(issues)
                else "audits found blockers"
            ),
            metadata={
                "dependencies_ok": dependencies.ok,
                "configuration_ok": configuration.ok,
                "backup_ok": backup.ok,
            },
        )

    def release_readiness(self) -> ReleaseStatus:
        """Return the overall release-readiness verdict."""
        contract, dependencies, configuration, _, backup, production_ready = (
            self._collect()
        )
        return self.reporter.release_readiness_status(
            contract, dependencies, configuration, backup, production_ready
        )

    def generate_release(self, sequence: int = 0) -> ReleaseReport:
        """Return the comprehensive final :class:`ReleaseReport`."""
        (
            contract,
            dependencies,
            configuration,
            documentation,
            backup,
            production_ready,
        ) = self._collect()
        return self.reporter.final_release_report(
            contract,
            dependencies,
            configuration,
            documentation,
            backup,
            production_ready,
            sequence,
        )

    def summary(self) -> ReleaseCandidateSummary:
        """Return the compact release-candidate go/no-go summary."""
        contract, dependencies, configuration, _, backup, production_ready = (
            self._collect()
        )
        return self.reporter.candidate_summary(
            contract,
            dependencies,
            configuration,
            backup,
            production_ready,
            grade=self.dashboard.overview().grade,
        )

    # --- helpers ---------------------------------------------------------
    def _collect(
        self,
    ) -> Tuple[
        ReleaseStatus,
        DependencyReport,
        ConfigurationAudit,
        DocumentationReport,
        BackupReport,
        bool,
    ]:
        """Run every release check once and return the pieces (one shared pass).

        Reads the platform's overall readiness through the dashboard (the single
        delegate) and runs each component's check, so every release output reflects the
        same snapshot. Deterministic; it runs nothing.
        """
        contract = self.contract.freeze_summary()
        dependencies = self.dependency.validate()
        configuration = self.configuration.validate()
        documentation = self.documentation.generate()
        backup = self.backup.validate()
        production_ready = self.dashboard.overview().ready
        return (
            contract,
            dependencies,
            configuration,
            documentation,
            backup,
            production_ready,
        )
