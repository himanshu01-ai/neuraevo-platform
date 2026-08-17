"""Release Candidate models (Sprint 16.15 — immutable release-infrastructure DTOs).

Provider-independent, immutable DTOs and enums for the Release Candidate backend — the
*release-preparation* surface that freezes the backend contracts, audits production
readiness, and generates release information over the frozen Sprint 16.14
:class:`DeveloperDashboardManager`. This sprint adds release infrastructure only: it
adds no business feature, redesigns no subsystem, never executes a workflow, and never
modifies platform state.

There is no deployment script, Docker/Kubernetes, CI/CD, cloud deployment, external
package manager, API redesign, or database migration anywhere — these carry only plain
data. Never a provider/SDK object crosses the boundary. Strictly additive to Sprints
1.x–16.14, whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# The version this release candidate prepares. A plain constant — no build system.
RELEASE_VERSION = "1.0.0-rc1"

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Enums
# =====================================================================
class ReleaseSeverity(str, Enum):
    """The allowed, deterministic severities of a release issue.

    ``INFO`` — informational. ``WARNING`` — a non-blocking concern. ``BLOCKER`` — a
    problem that blocks the release. Kept as a ``str`` enum so each serialises to its
    label.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


class ReleaseDecision(str, Enum):
    """The allowed, deterministic release go/no-go decisions.

    ``GO`` — the backend is a viable release candidate. ``NO_GO`` — a blocker remains.
    Kept as a ``str`` enum so each serialises to its label.
    """

    GO = "GO"
    NO_GO = "NO_GO"


# =====================================================================
# DTOs
# =====================================================================
class ReleaseIssue(BaseModel):
    """Immutable description of one release problem (no execution).

    ``frozen=True`` makes instances immutable. ``issue_id`` names the issue;
    ``severity`` is its :class:`ReleaseSeverity`; ``area`` names the release area it
    concerns (contract/dependency/configuration/documentation/backup/readiness);
    ``message`` is a deterministic description; ``detail`` is a plain-text note; and
    ``issue_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    issue_id: _NonEmptyStr
    severity: ReleaseSeverity
    area: str = ""
    message: _NonEmptyStr
    detail: str = ""
    issue_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReleaseStatus(BaseModel):
    """Immutable verdict of one release check (no execution).

    ``frozen=True`` makes instances immutable. ``name`` names the check; ``passed``
    mirrors whether it is free of ``BLOCKER`` issues; ``issues`` are the found
    :class:`ReleaseIssue` s; ``detail`` is a plain-text summary; and ``status_metadata``
    carries plain descriptors. Producing this DTO validates and runs nothing on its own.
    """

    model_config = ConfigDict(frozen=True)

    name: _NonEmptyStr
    passed: bool = False
    issues: List[ReleaseIssue] = Field(default_factory=list)
    detail: str = ""
    status_metadata: Dict[str, Any] = Field(default_factory=dict)


class DependencyReport(BaseModel):
    """Immutable result of the dependency audit (no execution).

    ``frozen=True`` makes instances immutable. ``ok`` is whether the audit is
    blocker-free; ``versions`` maps a core dependency name to its version; ``duplicates``
    lists any duplicated installed distribution; ``module_integrity`` is whether every
    platform module resolves; ``issues`` are the found :class:`ReleaseIssue` s; and
    ``report_metadata`` carries plain descriptors. This is a pure read — producing it
    runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool = False
    versions: Dict[str, str] = Field(default_factory=dict)
    duplicates: List[str] = Field(default_factory=list)
    module_integrity: bool = False
    issues: List[ReleaseIssue] = Field(default_factory=list)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfigurationAudit(BaseModel):
    """Immutable result of the configuration audit (no execution).

    ``frozen=True`` makes instances immutable. ``ok`` is whether the audit is
    blocker-free; ``complete`` is whether configuration validates; ``required_present``
    is whether every required key is present and non-empty; ``environment_compatible``
    is whether the environment is set; ``defaults`` is the effective configuration
    snapshot; ``issues`` are the found :class:`ReleaseIssue` s; and ``audit_metadata``
    carries plain descriptors. This is a pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool = False
    complete: bool = False
    required_present: bool = False
    environment_compatible: bool = False
    defaults: Dict[str, Any] = Field(default_factory=dict)
    issues: List[ReleaseIssue] = Field(default_factory=list)
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentationReport(BaseModel):
    """Immutable generated release documentation (no execution).

    ``frozen=True`` makes instances immutable. ``architecture_summary`` is a plain-text
    architecture description; ``module_inventory``, ``service_inventory``, and
    ``capability_inventory`` list the platform's modules, services, and capabilities;
    ``release_notes`` are the deterministic release-note lines; and ``doc_metadata``
    carries plain descriptors. This is a pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    architecture_summary: str = ""
    module_inventory: List[str] = Field(default_factory=list)
    service_inventory: List[str] = Field(default_factory=list)
    capability_inventory: List[str] = Field(default_factory=list)
    release_notes: List[str] = Field(default_factory=list)
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)


class BackupReport(BaseModel):
    """Immutable result of the backup/restore/snapshot audit (no execution).

    ``frozen=True`` makes instances immutable. ``ok`` is whether the audit is
    blocker-free; ``backup_integrity`` is whether a state snapshot serialises;
    ``restore_integrity`` is whether it round-trips losslessly; ``snapshot_consistency``
    is whether two snapshots of unchanged state are identical; ``issues`` are the found
    :class:`ReleaseIssue` s; and ``backup_metadata`` carries plain descriptors. This is a
    pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    ok: bool = False
    backup_integrity: bool = False
    restore_integrity: bool = False
    snapshot_consistency: bool = False
    issues: List[ReleaseIssue] = Field(default_factory=list)
    backup_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReleaseReport(BaseModel):
    """Immutable, comprehensive release-candidate report (no execution).

    ``frozen=True`` makes instances immutable. ``report_id`` names the report;
    ``version`` is the release version; ``decision`` is the :class:`ReleaseDecision`;
    ``ready`` is whether every gate passed; ``contract`` is the frozen-contract verdict;
    ``dependencies``, ``configuration``, ``documentation``, and ``backup`` are the audit
    reports; ``production_ready`` is the platform-readiness verdict; ``issues`` are the
    aggregated blockers; ``generated_sequence`` is a deterministic ordinal (an integer,
    never a clock time); and ``report_metadata`` carries plain descriptors. This is a
    pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    report_id: _NonEmptyStr
    version: str = RELEASE_VERSION
    decision: ReleaseDecision = ReleaseDecision.NO_GO
    ready: bool = False
    contract: ReleaseStatus
    dependencies: DependencyReport
    configuration: ConfigurationAudit
    documentation: DocumentationReport
    backup: BackupReport
    production_ready: bool = False
    issues: List[ReleaseIssue] = Field(default_factory=list)
    generated_sequence: int = Field(default=0, ge=0)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReleaseCandidateSummary(BaseModel):
    """Immutable compact release-candidate go/no-go summary (no execution).

    ``frozen=True`` makes instances immutable. ``version`` is the release version;
    ``decision`` is the :class:`ReleaseDecision`; ``ready`` is the overall verdict;
    ``production_ready``, ``contracts_frozen``, ``dependencies_ok``,
    ``configuration_ok``, and ``backup_ok`` are the individual gate verdicts;
    ``blocking_issues`` counts the blockers; ``grade`` is the experience grade;
    ``summary`` is a plain-text line; and ``summary_metadata`` carries plain descriptors.
    This is a pure read — producing it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    version: str = RELEASE_VERSION
    decision: ReleaseDecision = ReleaseDecision.NO_GO
    ready: bool = False
    production_ready: bool = False
    contracts_frozen: bool = False
    dependencies_ok: bool = False
    configuration_ok: bool = False
    backup_ok: bool = False
    blocking_issues: int = Field(default=0, ge=0)
    grade: str = ""
    summary: str = ""
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)
