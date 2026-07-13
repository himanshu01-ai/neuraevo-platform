"""Enterprise Operations Layer models (Sprint 16.11 — immutable operations DTOs).

Provider-independent, immutable DTOs and enums for the Enterprise Operations Layer —
the *operational* surface (authorization, audit, observability, configuration,
deployment validation, diagnostics) wrapped around the frozen Sprint 16.10
:class:`AIEmployeeService`. This layer adds operational capabilities only: it adds no
business functionality, modifies no workflow execution, and modifies no AI behavior.

There is no OAuth, JWT, SSO, LDAP, identity provider, cloud SDK, Prometheus,
OpenTelemetry, HTTP, or database anywhere. These carry only plain data and reuse the
frozen Sprint 16.10 :class:`HealthState` for component/overall health — never a
provider/SDK object crosses the boundary. Strictly additive to Sprints 1.x–16.10,
whose modules are left untouched.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Reuse the frozen Sprint 16.10 health vocabulary so component/overall health lines
# up exactly with what the HealthManager reports — no translation layer.
from app.services.ai_employee.service import HealthState

# Trimmed, required, non-empty string (whitespace-only fails validation).
_NonEmptyStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]


# =====================================================================
# Enums
# =====================================================================
class AuthorizationDecision(str, Enum):
    """The allowed, deterministic authorization decisions.

    ``ALLOW`` — the principal may perform the action. ``DENY`` — it may not. The
    mapping from principal/action to a decision lives in the *configurable* local
    authorization policy, not here. Kept as a ``str`` enum so each serialises to its
    label.
    """

    ALLOW = "ALLOW"
    DENY = "DENY"


class AuditCategory(str, Enum):
    """The allowed, deterministic categories of an audit record.

    ``TASK`` — a task operation. ``WORKFLOW`` — a workflow operation. ``APPROVAL`` —
    an approval decision. ``RECOVERY`` — a recovery action. ``ADMINISTRATIVE`` — an
    operational/administrative action. Kept as a ``str`` enum so each serialises to
    its label.
    """

    TASK = "TASK"
    WORKFLOW = "WORKFLOW"
    APPROVAL = "APPROVAL"
    RECOVERY = "RECOVERY"
    ADMINISTRATIVE = "ADMINISTRATIVE"


class CheckStatus(str, Enum):
    """The allowed, deterministic outcomes of a single deployment/config check.

    ``PASS`` — the check succeeded. ``WARN`` — non-blocking concern. ``FAIL`` — the
    check failed. Kept as a ``str`` enum so each serialises to its label.
    """

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


# =====================================================================
# DTOs
# =====================================================================
class AuthorizationResult(BaseModel):
    """Immutable outcome of an authorization check (no authentication, no execution).

    ``frozen=True`` makes instances immutable. ``allowed`` is the boolean decision;
    ``decision`` is the matching :class:`AuthorizationDecision`; ``principal`` is who
    was checked; ``action`` and ``resource`` are what was checked; ``reason`` is a
    plain-text rationale; and ``result_metadata`` carries plain descriptors. Producing
    this DTO authenticates nothing and runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    allowed: bool
    decision: AuthorizationDecision
    principal: str = ""
    action: str = ""
    resource: str = ""
    reason: str = ""
    result_metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditRecord(BaseModel):
    """Immutable audit record of one tracked operation (append-only, never mutated).

    ``frozen=True`` makes instances immutable. ``record_id`` names the record;
    ``category`` is its :class:`AuditCategory`; ``action`` is the operation;
    ``principal`` is who performed it; ``resource`` is what it targeted; ``outcome``
    is the deterministic result label; ``sequence`` is a deterministic ordinal (an
    integer, never a clock time); ``detail`` is a plain-text note; and
    ``record_metadata`` carries plain descriptors. Producing this DTO runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    record_id: _NonEmptyStr
    category: AuditCategory
    action: _NonEmptyStr
    principal: str = "system"
    resource: str = ""
    outcome: str = ""
    sequence: int = Field(default=0, ge=0)
    detail: str = ""
    record_metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditQuery(BaseModel):
    """Immutable filter over the audit history (no execution).

    ``frozen=True`` makes instances immutable. A field left ``None`` is not filtered
    on: ``category``/``principal``/``action``/``resource`` are exact matches;
    ``text`` is a case-insensitive substring across the record's fields; ``limit``
    caps the number of results (in chronological order); and ``query_metadata``
    carries plain descriptors. Producing this DTO queries nothing on its own.
    """

    model_config = ConfigDict(frozen=True)

    category: Optional[AuditCategory] = None
    principal: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    text: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=0)
    query_metadata: Dict[str, Any] = Field(default_factory=dict)


class MetricSnapshot(BaseModel):
    """Immutable snapshot of deterministic operational counters (no execution).

    ``frozen=True`` makes instances immutable. ``name`` labels the snapshot (e.g.
    ``"metrics"``, ``"execution"``, ``"service"``); ``metrics`` maps counter names to
    integer values captured from platform state; and ``snapshot_metadata`` carries
    plain descriptors. This is a pure read — producing it runs and collects from no
    external telemetry system.
    """

    model_config = ConfigDict(frozen=True)

    name: str = ""
    metrics: Dict[str, int] = Field(default_factory=dict)
    snapshot_metadata: Dict[str, Any] = Field(default_factory=dict)


class ComponentStatus(BaseModel):
    """Immutable status of one platform subsystem (no execution).

    ``frozen=True`` makes instances immutable. ``name`` names the subsystem;
    ``state`` is its :class:`HealthState`; ``healthy`` mirrors whether it is
    ``HEALTHY``; ``detail`` is a plain-text note; and ``status_metadata`` carries
    plain descriptors. Producing this DTO calls no subsystem and runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    name: _NonEmptyStr
    state: HealthState
    healthy: bool = False
    detail: str = ""
    status_metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfigurationReport(BaseModel):
    """Immutable result of validating platform configuration (no execution).

    ``frozen=True`` makes instances immutable. ``valid`` is whether the configuration
    passed; ``issues`` are the blocking problems (deterministic messages);
    ``warnings`` are non-blocking concerns; ``settings`` is the validated
    configuration snapshot; and ``report_metadata`` carries plain descriptors.
    Producing this DTO loads and runs nothing.
    """

    model_config = ConfigDict(frozen=True)

    valid: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class DeploymentReport(BaseModel):
    """Immutable result of a deployment-readiness validation (no execution).

    ``frozen=True`` makes instances immutable. ``ready`` is whether the checked scope
    is deployment-ready; ``checks`` maps each check name to a :class:`CheckStatus`
    label; ``issues`` are the deterministic failure messages; ``detail`` names the
    scope (``"dependencies"``/``"components"``/``"configuration"``/``"startup"``); and
    ``report_metadata`` carries plain descriptors. Producing this DTO deploys and runs
    nothing.
    """

    model_config = ConfigDict(frozen=True)

    ready: bool
    checks: Dict[str, str] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    detail: str = ""
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticsReport(BaseModel):
    """Immutable diagnostics report over the platform (no execution).

    ``frozen=True`` makes instances immutable. ``healthy`` is whether the diagnosed
    scope is healthy; ``summary`` is a plain-text summary; ``components`` are the
    per-subsystem :class:`ComponentStatus`\\ es; ``dependencies`` maps a dependency
    name to its check label; ``metrics`` is an optional :class:`MetricSnapshot`;
    ``issues`` are the deterministic problem messages; and ``report_metadata`` carries
    plain descriptors. Producing this DTO monitors and runs nothing externally.
    """

    model_config = ConfigDict(frozen=True)

    healthy: bool
    summary: str = ""
    components: List[ComponentStatus] = Field(default_factory=list)
    dependencies: Dict[str, str] = Field(default_factory=dict)
    metrics: Optional[MetricSnapshot] = None
    issues: List[str] = Field(default_factory=list)
    report_metadata: Dict[str, Any] = Field(default_factory=dict)


class EnterpriseStatus(BaseModel):
    """Immutable, provider-independent enterprise-wide status (no execution).

    ``frozen=True`` makes instances immutable. ``state`` is the overall
    :class:`HealthState`; ``ready`` is whether every subsystem is up; ``components``
    are the per-subsystem :class:`ComponentStatus`\\ es; ``metrics`` is the aggregate
    :class:`MetricSnapshot`; ``audit_record_count`` is how many audit records exist;
    ``detail`` is a plain-text summary; and ``status_metadata`` carries plain
    descriptors. Producing this DTO runs nothing and exposes no provider object.
    """

    model_config = ConfigDict(frozen=True)

    state: HealthState
    ready: bool = False
    components: List[ComponentStatus] = Field(default_factory=list)
    metrics: Optional[MetricSnapshot] = None
    audit_record_count: int = Field(default=0, ge=0)
    detail: str = ""
    status_metadata: Dict[str, Any] = Field(default_factory=dict)
