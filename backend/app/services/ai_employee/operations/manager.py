"""Enterprise operations manager (Sprint 16.11 — coordinate enterprise operations).

Defines :class:`EnterpriseOperationsManager`, the coordinator of the Enterprise
Operations Layer. It coordinates the platform's operational surface over its injected
managers — the :class:`AuthorizationManager`, :class:`AuditManager`,
:class:`ObservabilityManager`, :class:`ConfigurationManager`,
:class:`DeploymentValidator`, and :class:`DiagnosticsManager` — and *delegates every
business request to the frozen Sprint 16.10* :class:`AIEmployeeService`:

    validate_environment   (deployment-readiness verdict + audit)
    audit                  (read/filter the audit trail)
    authorize              (local authorization decision + audit)
    diagnostics            (aggregate diagnostics report)
    system_status          (enterprise-wide status)
    submit_task            (delegate a business request to the service, audited)

It adds operational capabilities only: it adds no business functionality, modifies no
workflow execution, and modifies no AI behaviour. It never executes a workflow or a
capability itself and never calls the Workflow Coordinator — business work goes only
through the :class:`AIEmployeeService`. Constructor injection only; it holds no
mutable state of its own (the audit ledger lives in the :class:`AuditManager`) — no
static, singleton, or service-locator state. Strictly additive to Sprints 1.x–16.10,
whose modules are left untouched.
"""

from typing import Any, Dict, List, Optional

from app.services.ai_employee.operations.audit import AuditManager
from app.services.ai_employee.operations.authorization import (
    AuthorizationManager,
)
from app.services.ai_employee.operations.configuration import (
    ConfigurationManager,
)
from app.services.ai_employee.operations.deployment import DeploymentValidator
from app.services.ai_employee.operations.diagnostics import DiagnosticsManager
from app.services.ai_employee.operations.models import (
    AuditQuery,
    AuditRecord,
    AuthorizationResult,
    ConfigurationReport,
    DeploymentReport,
    DiagnosticsReport,
    EnterpriseStatus,
)
from app.services.ai_employee.operations.observability import (
    ObservabilityManager,
)
from app.services.ai_employee.service import (
    HealthState,
    TaskSubmissionRequest,
    TaskSubmissionResponse,
)


class EnterpriseOperationsManager:
    """Coordinates enterprise operations over its managers and the AIEmployeeService.

    Constructed with an injected :class:`AuthorizationManager`, :class:`AuditManager`,
    :class:`ObservabilityManager`, :class:`ConfigurationManager`,
    :class:`DeploymentValidator`, :class:`DiagnosticsManager`, and the frozen Sprint
    16.10 :class:`AIEmployeeService` (constructor injection; it instantiates none). It
    authorizes, audits, validates the environment, diagnoses, and reports
    enterprise-wide status, and delegates every business request to the
    :class:`AIEmployeeService` — it executes no workflow or capability itself. It holds
    no mutable state of its own.
    """

    def __init__(
        self,
        authorization: AuthorizationManager,
        audit: AuditManager,
        observability: ObservabilityManager,
        configuration: ConfigurationManager,
        deployment: DeploymentValidator,
        diagnostics: DiagnosticsManager,
        service,
    ) -> None:
        self.authorization = authorization
        self.audit_manager = audit
        self.observability = observability
        self.configuration = configuration
        self.deployment = deployment
        self.diagnostics_manager = diagnostics
        self.service = service

    # --- authorization ---------------------------------------------------
    def authorize(
        self, principal: str, action: str, resource: str = ""
    ) -> AuthorizationResult:
        """Return the local authorization decision for the request and audit it."""
        result = self.authorization.authorize(principal, action, resource)
        self.audit_manager.record_administrative(
            action=f"authorize:{action}",
            principal=principal,
            resource=resource,
            outcome=result.decision.value,
        )
        return result

    # --- audit -----------------------------------------------------------
    def audit(
        self, query: Optional[AuditQuery] = None
    ) -> List[AuditRecord]:
        """Return the full audit trail, or the records matching ``query``."""
        if query is None:
            return self.audit_manager.history()
        return self.audit_manager.filter(query)

    # --- configuration / deployment -------------------------------------
    def validate_configuration(
        self, config: Optional[Dict[str, Any]] = None
    ) -> ConfigurationReport:
        """Validate ``config`` (or the loaded defaults) and return the report."""
        effective = (
            self.configuration.load() if config is None else config
        )
        return self.configuration.validate(effective)

    def validate_environment(
        self, config: Optional[Dict[str, Any]] = None
    ) -> DeploymentReport:
        """Return the deployment-readiness verdict for the environment and audit it."""
        effective = (
            self.configuration.load() if config is None else config
        )
        report = self.deployment.validate_startup(effective)
        self.audit_manager.record_administrative(
            action="validate_environment",
            outcome="ready" if report.ready else "not_ready",
        )
        return report

    # --- diagnostics -----------------------------------------------------
    def diagnostics(self) -> DiagnosticsReport:
        """Return the aggregate diagnostics report."""
        return self.diagnostics_manager.diagnostics()

    def system_report(self) -> DiagnosticsReport:
        """Return the full system diagnostics report (components + deps + metrics)."""
        return self.diagnostics_manager.system_report()

    # --- status ----------------------------------------------------------
    def system_status(self) -> EnterpriseStatus:
        """Return the enterprise-wide :class:`EnterpriseStatus` (health + metrics)."""
        components = self.observability.component_status()
        metrics = self.observability.metrics()
        up = sum(1 for component in components if component.healthy)
        total = len(components)
        if total and up == total:
            state = HealthState.HEALTHY
        elif up == 0:
            state = HealthState.UNHEALTHY
        else:
            state = HealthState.DEGRADED
        return EnterpriseStatus(
            state=state,
            ready=bool(total) and up == total,
            components=components,
            metrics=metrics,
            audit_record_count=len(self.audit_manager.history()),
            detail=f"{up}/{total} subsystems healthy",
        )

    # --- business delegation --------------------------------------------
    def submit_task(
        self, request: TaskSubmissionRequest
    ) -> TaskSubmissionResponse:
        """Delegate a business task submission to the :class:`AIEmployeeService`, audited.

        The operations layer never executes work itself: it forwards the request to
        the frozen Sprint 16.10 service (the only path to the :class:`AIEmployee`) and
        records the outcome in the audit trail. It calls no Workflow Coordinator and
        no capability.
        """
        response = self.service.submit_task(request)
        self.audit_manager.record_task(
            action="submit_task",
            resource=request.task_id,
            outcome="accepted" if response.accepted else "rejected",
        )
        return response
