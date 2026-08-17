"""Enterprise Operations Layer package (Sprint 16.11 — operational capabilities).

Adds the enterprise *operational* surface — authorization, audit, observability,
configuration, deployment validation, and diagnostics — wrapped around the frozen
Sprint 16.10 :class:`AIEmployeeService`. It adds operational capabilities only: no
business functionality, no change to workflow execution, and no change to AI
behaviour. Business work is delegated to the :class:`AIEmployeeService` alone; the
layer executes no workflow or capability, calls no Workflow Coordinator, and connects
to no OAuth/SSO/LDAP identity provider, cloud SDK, Prometheus/OpenTelemetry monitor,
HTTP transport, or database. It follows the flow ``EnterpriseOperationsManager ->
{AuthorizationManager, AuditManager, ObservabilityManager, ConfigurationManager,
DeploymentValidator, DiagnosticsManager}`` over the :class:`AIEmployeeService`:

* the immutable DTOs :class:`AuthorizationResult`, :class:`AuditRecord`,
  :class:`AuditQuery`, :class:`MetricSnapshot`, :class:`ComponentStatus`,
  :class:`ConfigurationReport`, :class:`DeploymentReport`, :class:`DiagnosticsReport`,
  and :class:`EnterpriseStatus`, plus the :class:`AuthorizationDecision`,
  :class:`AuditCategory`, and :class:`CheckStatus` enums;
* the :class:`AuthorizationManager` abstraction with the local
  :class:`LocalAuthorizationManager`;
* the :class:`AuditManager`, :class:`ObservabilityManager`,
  :class:`ConfigurationManager`, :class:`DeploymentValidator`, and
  :class:`DiagnosticsManager`; and
* the :class:`EnterpriseOperationsManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.10.
"""

from app.services.ai_employee.operations.audit import AuditManager
from app.services.ai_employee.operations.authorization import (
    AuthorizationManager,
    LocalAuthorizationManager,
)
from app.services.ai_employee.operations.configuration import (
    ConfigurationManager,
)
from app.services.ai_employee.operations.deployment import DeploymentValidator
from app.services.ai_employee.operations.diagnostics import DiagnosticsManager
from app.services.ai_employee.operations.manager import (
    EnterpriseOperationsManager,
)
from app.services.ai_employee.operations.models import (
    AuditCategory,
    AuditQuery,
    AuditRecord,
    AuthorizationDecision,
    AuthorizationResult,
    CheckStatus,
    ComponentStatus,
    ConfigurationReport,
    DeploymentReport,
    DiagnosticsReport,
    EnterpriseStatus,
    MetricSnapshot,
)
from app.services.ai_employee.operations.observability import (
    ObservabilityManager,
)

__all__ = [
    # DTOs
    "AuthorizationResult",
    "AuditRecord",
    "AuditQuery",
    "MetricSnapshot",
    "ComponentStatus",
    "ConfigurationReport",
    "DeploymentReport",
    "DiagnosticsReport",
    "EnterpriseStatus",
    # enums
    "AuthorizationDecision",
    "AuditCategory",
    "CheckStatus",
    # managers
    "AuthorizationManager",
    "LocalAuthorizationManager",
    "AuditManager",
    "ObservabilityManager",
    "ConfigurationManager",
    "DeploymentValidator",
    "DiagnosticsManager",
    "EnterpriseOperationsManager",
]
