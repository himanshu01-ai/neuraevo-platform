"""Release reporter (Sprint 16.15 — assemble release reports and the go/no-go).

Defines :class:`ReleaseReporter`, which assembles the already-computed contract verdict
and audit reports into the release outputs — the release-readiness status, the final
:class:`ReleaseReport`, and the compact :class:`ReleaseCandidateSummary` with its
:class:`ReleaseDecision`.

It is a pure formatter: it composes the pieces it is given, aggregates their blocking
issues, and derives the go/no-go — executing nothing beyond deterministic assembly.
There is no deployment, package manager, or external system. Strictly additive to
Sprints 1.x–16.14, whose modules are left untouched.
"""

from typing import List

from app.services.ai_employee.release import common
from app.services.ai_employee.release.models import (
    RELEASE_VERSION,
    BackupReport,
    ConfigurationAudit,
    DependencyReport,
    DocumentationReport,
    ReleaseCandidateSummary,
    ReleaseDecision,
    ReleaseIssue,
    ReleaseReport,
    ReleaseStatus,
)


class ReleaseReporter:
    """Assembles release reports and the release decision (pure assembly, no execution).

    Stateless. ``release_readiness_status`` folds every gate into a
    :class:`ReleaseStatus`; ``final_release_report`` assembles the comprehensive
    :class:`ReleaseReport`; and ``candidate_summary`` assembles the compact
    :class:`ReleaseCandidateSummary` with its :class:`ReleaseDecision`. It reads the
    pieces it is given only — it runs nothing.
    """

    def release_readiness_status(
        self,
        contract: ReleaseStatus,
        dependencies: DependencyReport,
        configuration: ConfigurationAudit,
        backup: BackupReport,
        production_ready: bool,
    ) -> ReleaseStatus:
        """Fold every gate into the release-readiness :class:`ReleaseStatus`."""
        issues = self._aggregate_blockers(
            contract, dependencies, configuration, backup, production_ready
        )
        return common.status(
            "release_readiness",
            issues,
            detail=(
                "release candidate is ready"
                if not issues
                else f"{len(issues)} blocker(s) remain"
            ),
            metadata={"production_ready": production_ready},
        )

    def final_release_report(
        self,
        contract: ReleaseStatus,
        dependencies: DependencyReport,
        configuration: ConfigurationAudit,
        documentation: DocumentationReport,
        backup: BackupReport,
        production_ready: bool,
        sequence: int = 0,
    ) -> ReleaseReport:
        """Assemble the comprehensive final :class:`ReleaseReport`."""
        issues = self._aggregate_blockers(
            contract, dependencies, configuration, backup, production_ready
        )
        ready = not issues
        return ReleaseReport(
            report_id="release-final",
            version=RELEASE_VERSION,
            decision=(
                ReleaseDecision.GO if ready else ReleaseDecision.NO_GO
            ),
            ready=ready,
            contract=contract,
            dependencies=dependencies,
            configuration=configuration,
            documentation=documentation,
            backup=backup,
            production_ready=production_ready,
            issues=issues,
            generated_sequence=sequence,
            report_metadata={"blocking_issue_count": len(issues)},
        )

    def candidate_summary(
        self,
        contract: ReleaseStatus,
        dependencies: DependencyReport,
        configuration: ConfigurationAudit,
        backup: BackupReport,
        production_ready: bool,
        grade: str = "",
    ) -> ReleaseCandidateSummary:
        """Assemble the compact :class:`ReleaseCandidateSummary` with the decision."""
        issues = self._aggregate_blockers(
            contract, dependencies, configuration, backup, production_ready
        )
        ready = not issues
        return ReleaseCandidateSummary(
            version=RELEASE_VERSION,
            decision=(
                ReleaseDecision.GO if ready else ReleaseDecision.NO_GO
            ),
            ready=ready,
            production_ready=production_ready,
            contracts_frozen=contract.passed,
            dependencies_ok=dependencies.ok,
            configuration_ok=configuration.ok,
            backup_ok=backup.ok,
            blocking_issues=len(issues),
            grade=grade,
            summary=(
                f"{RELEASE_VERSION}: "
                f"{'GO' if ready else 'NO_GO'}; "
                f"{len(issues)} blocker(s)"
            ),
            summary_metadata={"grade": grade},
        )

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _aggregate_blockers(
        contract: ReleaseStatus,
        dependencies: DependencyReport,
        configuration: ConfigurationAudit,
        backup: BackupReport,
        production_ready: bool,
    ) -> List[ReleaseIssue]:
        """Return every blocking issue across the gates (production adds one if down)."""
        issues: List[ReleaseIssue] = []
        issues.extend(common.blockers(contract.issues))
        issues.extend(common.blockers(dependencies.issues))
        issues.extend(common.blockers(configuration.issues))
        issues.extend(common.blockers(backup.issues))
        if not production_ready:
            issues.append(
                common.issue(
                    issue_id="release-production-not-ready",
                    message="production validation is not ready",
                    area="readiness",
                )
            )
        return issues
