"""Release Candidate package (Sprint 16.15 — prepare the backend for v1.0 RC).

Adds the Release Candidate backend — a provider-independent, *release-preparation*
surface that freezes the backend contracts, audits production readiness, and generates
release information over the frozen Sprint 16.14 :class:`DeveloperDashboardManager`.
This sprint adds release infrastructure only: it adds no business feature, redesigns no
subsystem, never executes a workflow, and never modifies platform state. The platform's
overall state is read through the frozen :class:`DeveloperDashboardManager` (and, as
allowed, the production/operations/experience managers), and it connects to no
deployment script, Docker/Kubernetes, CI/CD, cloud, external package manager, or
database migration. It follows the flow ``ReleaseManager -> {ContractManager,
DependencyAuditor, ConfigurationAuditor, DocumentationGenerator, BackupValidator,
ReleaseReporter}`` over the :class:`DeveloperDashboardManager`:

* the immutable DTOs :class:`ReleaseStatus`, :class:`ReleaseIssue`,
  :class:`DependencyReport`, :class:`ConfigurationAudit`, :class:`DocumentationReport`,
  :class:`BackupReport`, :class:`ReleaseReport`, and :class:`ReleaseCandidateSummary`,
  plus the :class:`ReleaseSeverity` and :class:`ReleaseDecision` enums and the
  ``RELEASE_VERSION`` constant;
* the :class:`ContractManager`, :class:`DependencyAuditor`,
  :class:`ConfigurationAuditor`, :class:`DocumentationGenerator`,
  :class:`BackupValidator`, and :class:`ReleaseReporter`; and
* the :class:`ReleaseManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.14.
"""

from app.services.ai_employee.release.backup_validator import BackupValidator
from app.services.ai_employee.release.configuration_auditor import (
    ConfigurationAuditor,
)
from app.services.ai_employee.release.contract_manager import ContractManager
from app.services.ai_employee.release.dependency_auditor import (
    DependencyAuditor,
)
from app.services.ai_employee.release.documentation_generator import (
    DocumentationGenerator,
)
from app.services.ai_employee.release.manager import ReleaseManager
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
    ReleaseSeverity,
    ReleaseStatus,
)
from app.services.ai_employee.release.reporter import ReleaseReporter

__all__ = [
    # constant
    "RELEASE_VERSION",
    # DTOs
    "ReleaseStatus",
    "ReleaseIssue",
    "DependencyReport",
    "ConfigurationAudit",
    "DocumentationReport",
    "BackupReport",
    "ReleaseReport",
    "ReleaseCandidateSummary",
    # enums
    "ReleaseSeverity",
    "ReleaseDecision",
    # components / manager
    "ContractManager",
    "DependencyAuditor",
    "ConfigurationAuditor",
    "DocumentationGenerator",
    "BackupValidator",
    "ReleaseReporter",
    "ReleaseManager",
]
