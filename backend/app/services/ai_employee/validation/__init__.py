"""Production Validation Platform package (Sprint 16.13 — validate production readiness).

Adds the Production Validation Platform — a provider-independent, *validation* surface
that checks the AI Employee platform is production-ready over the frozen Sprint 16.11
:class:`EnterpriseOperationsManager`. This platform validates only: it never executes a
workflow or a capability, never calls the Workflow Coordinator, and never changes AI
behaviour or modifies an existing service. Platform state is read only through the
:class:`EnterpriseOperationsManager`, and it connects to no load generator, stress tool,
real benchmark, penetration test, cloud validator, Docker/Kubernetes, CI/CD, or
external scanner. It follows the flow ``ProductionValidationManager -> {SystemValidator,
IntegrationValidator, PerformanceValidator, ReliabilityValidator, SecurityValidator,
CompatibilityValidator, ValidationReporter}`` over the
:class:`EnterpriseOperationsManager`:

* the immutable DTOs :class:`ValidationResult`, :class:`ValidationIssue`,
  :class:`ValidationReport`, :class:`SystemStatus`, :class:`IntegrationStatus`,
  :class:`PerformanceSummary`, :class:`ReliabilitySummary`, and
  :class:`ProductionReadiness`, plus the :class:`ValidationStatus`,
  :class:`ValidationSeverity`, and :class:`ValidationScope` enums;
* the :class:`SystemValidator`, :class:`IntegrationValidator`,
  :class:`PerformanceValidator`, :class:`ReliabilityValidator`,
  :class:`SecurityValidator`, :class:`CompatibilityValidator`, and
  :class:`ValidationReporter`; and
* the :class:`ProductionValidationManager` coordinator.

This package is strictly additive to — and leaves untouched — every frozen sprint
through 16.12.
"""

from app.services.ai_employee.validation.compatibility_validator import (
    CompatibilityValidator,
)
from app.services.ai_employee.validation.integration_validator import (
    IntegrationValidator,
)
from app.services.ai_employee.validation.manager import (
    ProductionValidationManager,
)
from app.services.ai_employee.validation.models import (
    IntegrationStatus,
    PerformanceSummary,
    ProductionReadiness,
    ReliabilitySummary,
    SystemStatus,
    ValidationIssue,
    ValidationReport,
    ValidationResult,
    ValidationScope,
    ValidationSeverity,
    ValidationStatus,
)
from app.services.ai_employee.validation.performance_validator import (
    PerformanceValidator,
)
from app.services.ai_employee.validation.reliability_validator import (
    ReliabilityValidator,
)
from app.services.ai_employee.validation.reporter import ValidationReporter
from app.services.ai_employee.validation.security_validator import (
    SecurityValidator,
)
from app.services.ai_employee.validation.system_validator import (
    SystemValidator,
)

__all__ = [
    # DTOs
    "ValidationResult",
    "ValidationIssue",
    "ValidationReport",
    "SystemStatus",
    "IntegrationStatus",
    "PerformanceSummary",
    "ReliabilitySummary",
    "ProductionReadiness",
    # enums
    "ValidationStatus",
    "ValidationSeverity",
    "ValidationScope",
    # validators / reporter / manager
    "SystemValidator",
    "IntegrationValidator",
    "PerformanceValidator",
    "ReliabilityValidator",
    "SecurityValidator",
    "CompatibilityValidator",
    "ValidationReporter",
    "ProductionValidationManager",
]
