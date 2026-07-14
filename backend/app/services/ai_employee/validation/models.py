"""Production Validation Platform models (Sprint 16.13 — immutable validation DTOs).

Provider-independent, immutable DTOs and enums for the Production Validation Platform —
the *validation* surface that checks the AI Employee platform is production-ready over
the frozen Sprint 16.11 :class:`EnterpriseOperationsManager`. This platform validates
only: it never executes a workflow, never changes AI behaviour, and never modifies an
existing service. It reads platform state and produces deterministic validation
verdicts.

There is no load generator, stress tool, real benchmark, penetration test, cloud
validator, Docker/Kubernetes, CI/CD, or external scanner anywhere — these carry only
plain data, and they reuse the frozen Sprint 16.10 :class:`HealthState` for health
verdicts. Never a provider/SDK object crosses the boundary. Strictly additive to
Sprints 1.x–16.12, whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Reuse the frozen Sprint 16.10 health vocabulary so subsystem/overall health lines up
# exactly with what the HealthManager reports — no translation layer.
from app.services.ai_employee.service import HealthState

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Enums
# =====================================================================
class ValidationStatus(str, Enum):
    """The allowed, deterministic outcomes of a validation.

    ``PASSED`` — no blocking problem. ``WARNING`` — a non-blocking concern was found.
    ``FAILED`` — a blocking problem was found. Kept as a ``str`` enum so each serialises
    to its label.
    """

    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


class ValidationSeverity(str, Enum):
    """The allowed, deterministic severities of a validation issue.

    ``INFO`` — informational. ``WARNING`` — a non-blocking concern. ``ERROR`` — a
    blocking problem. Kept as a ``str`` enum so each serialises to its label.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationScope(str, Enum):
    """The allowed, deterministic scopes a validation or report can cover.

    ``SYSTEM``, ``INTEGRATION``, ``PERFORMANCE``, ``RELIABILITY``, ``SECURITY``, and
    ``COMPATIBILITY`` are the per-validator scopes; ``READINESS`` is the aggregate
    production-readiness verdict; ``FINAL`` is the combined report. Kept as a ``str``
    enum so each serialises to its label.
    """

    SYSTEM = "SYSTEM"
    INTEGRATION = "INTEGRATION"
    PERFORMANCE = "PERFORMANCE"
    RELIABILITY = "RELIABILITY"
    SECURITY = "SECURITY"
    COMPATIBILITY = "COMPATIBILITY"
    READINESS = "READINESS"
    FINAL = "FINAL"


# =====================================================================
# DTOs
# =====================================================================
class ValidationIssue(BaseModel):
    """Immutable description of one validation problem (no execution).

    ``frozen=True`` makes instances immutable. ``issue_id`` names the issue;
    ``severity`` is its :class:`ValidationSeverity`; ``component`` names what it
    concerns; ``message`` is a deterministic description; ``detail`` is a plain-text
    note; and ``issue_metadata`` carries plain descriptors. Producing this DTO runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    issue_id: _NonEmptyStr
    severity: ValidationSeverity
    component: str = ""
    message: _NonEmptyStr
    detail: str = ""
    issue_metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Immutable outcome of one validation (no execution).

    ``frozen=True`` makes instances immutable. ``name`` names the validation;
    ``scope`` is its :class:`ValidationScope`; ``status`` its :class:`ValidationStatus`;
    ``passed`` mirrors whether it is free of blocking (``ERROR``) issues; ``issues`` are
    the found :class:`ValidationIssue` s; ``detail`` is a plain-text summary; and
    ``result_metadata`` carries plain descriptors. Producing this DTO validates and runs
    nothing on its own.
    """

    model_config = ConfigDict(frozen=True)

    name: _NonEmptyStr
    scope: ValidationScope
    status: ValidationStatus
    passed: bool = False
    issues: List[ValidationIssue] = Field(default_factory=list)
    detail: str = ""
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Immutable report bundling validation results for a scope (no execution).

    ``frozen=True`` makes instances immutable. ``report_id`` names the report;
    ``scope`` is its :class:`ValidationScope`; ``passed`` is whether every bundled
    result passed; ``results`` are the bundled :class:`ValidationResult` s; ``issues``
    are the aggregated :class:`ValidationIssue` s; ``summary`` is a plain-text summary;
    ``generated_sequence`` is a deterministic ordinal (an integer, never a clock time);
    and ``report_metadata`` carries plain descriptors. This is a pure read — producing
    it runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    report_id: _NonEmptyStr
    scope: ValidationScope
    passed: bool = False
    results: List[ValidationResult] = Field(default_factory=list)
    issues: List[ValidationIssue] = Field(default_factory=list)
    summary: str = ""
    generated_sequence: int = Field(default=0, ge=0)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    """Immutable status of one validated platform subsystem (no execution).

    ``frozen=True`` makes instances immutable. ``name`` names the subsystem;
    ``present`` is whether it is wired into the platform; ``healthy`` mirrors whether it
    is up; ``state`` is its :class:`HealthState`; ``detail`` is a plain-text note; and
    ``status_metadata`` carries plain descriptors. Producing this DTO calls no subsystem
    and runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    name: _NonEmptyStr
    present: bool = False
    healthy: bool = False
    state: HealthState = HealthState.UNHEALTHY
    detail: str = ""
    status_metadata: Dict[str, Any] = Field(default_factory=dict)


class IntegrationStatus(BaseModel):
    """Immutable status of one validated integration point (no execution).

    ``frozen=True`` makes instances immutable. ``name`` names the integration (e.g.
    ``"Planning <-> Runtime"``); ``source`` and ``target`` name the two sides;
    ``connected`` is whether both sides are wired; ``consistent`` is whether their
    wiring is coherent (both healthy, or a shared instance where expected); ``detail`` is
    a plain-text note; and ``status_metadata`` carries plain descriptors. Producing this
    DTO exercises no interaction and runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    name: _NonEmptyStr
    source: str = ""
    target: str = ""
    connected: bool = False
    consistent: bool = False
    detail: str = ""
    status_metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformanceSummary(BaseModel):
    """Immutable summary of deterministic performance counters (no execution).

    ``frozen=True`` makes instances immutable. ``execution`` maps execution counters to
    integer values; ``throughput`` maps processed-work counters to integer values;
    ``response`` maps response-quality ratios to float values; ``resource_usage`` maps
    resource counters to integer values; and ``summary_metadata`` carries plain
    descriptors. These are pure reads of platform state — no timer, benchmark, or load
    generator is involved. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    execution: Dict[str, int] = Field(default_factory=dict)
    throughput: Dict[str, int] = Field(default_factory=dict)
    response: Dict[str, float] = Field(default_factory=dict)
    resource_usage: Dict[str, int] = Field(default_factory=dict)
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)


class ReliabilitySummary(BaseModel):
    """Immutable summary of the platform's reliability checks (no execution).

    ``frozen=True`` makes instances immutable. ``recovery_ready``,
    ``workflow_consistent``, ``deterministic``, ``state_consistent``, and
    ``dependency_integrity`` are the individual deterministic checks; ``reliable``
    mirrors whether all five hold; ``detail`` is a plain-text summary; and
    ``summary_metadata`` carries plain descriptors. This is a pure read — producing it
    runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    recovery_ready: bool = False
    workflow_consistent: bool = False
    deterministic: bool = False
    state_consistent: bool = False
    dependency_integrity: bool = False
    reliable: bool = False
    detail: str = ""
    summary_metadata: Dict[str, Any] = Field(default_factory=dict)


class ProductionReadiness(BaseModel):
    """Immutable production-readiness verdict for the platform (no execution).

    ``frozen=True`` makes instances immutable. ``ready`` is the go/no-go verdict;
    ``state`` is the platform's overall :class:`HealthState`; ``passed_validations`` and
    ``total_validations`` count the validation results; ``blocking_issues`` are the
    ``ERROR``-severity :class:`ValidationIssue` s that block readiness; ``results`` are
    the per-scope :class:`ValidationResult` s (may be empty for a compact summary);
    ``detail`` is a plain-text summary; and ``readiness_metadata`` carries plain
    descriptors. This is a pure read — producing it runs nothing and exposes no provider
    object.
    """

    model_config = ConfigDict(frozen=True)

    ready: bool = False
    state: HealthState = HealthState.UNHEALTHY
    passed_validations: int = Field(default=0, ge=0)
    total_validations: int = Field(default=0, ge=0)
    blocking_issues: List[ValidationIssue] = Field(default_factory=list)
    results: List[ValidationResult] = Field(default_factory=list)
    detail: str = ""
    readiness_metadata: Dict[str, Any] = Field(default_factory=dict)
